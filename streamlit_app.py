import os
from datetime import datetime, timedelta
import io 
import numpy as np
import pandas as pd
import rasterio
import streamlit as st
import requests

import ee
import geopandas as gpd
import cv2

import matplotlib.pyplot as plt

from scrapers.ffc_scraper import get_ffc_data
from engine.ai_alerts import FloodAI
from models.model_inference import load_flood_model, predict_flood, resolve_weights_path
from utils.ndwi import get_flood_mask, FLOOD_START, FLOOD_END
from utils.districts import detect_name_column, shapely_to_ee, PRIORITY_DISTRICTS, flood_percent_for_district


SHAPEFILE = "pakistan_districts.json"
PROJECT_ID = os.getenv("PROJECT_ID")

st.set_page_config(page_title="FloodSense-PK Dashboard", layout="wide")


def inject_dark_theme():
    # Optional CSS for a cleaner, non-overlapping look.
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; }
        .stMetric { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px; }
        .stTabs button { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06) !important; border-radius: 10px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_dark_theme()


def init_gee():
    try:
        if PROJECT_ID:
            ee.Initialize(project=PROJECT_ID)
        else:
            ee.Initialize()
        return True
    except Exception as e:
        st.error(f"GEE init failed: {e}")
        st.write("Run: earthengine authenticate")
        return False

def preprocess_image(tif_bytes):
    """
    Accepts raw GeoTIFF bytes (single-band VV from GEE).
    Returns (tensor [1,3,256,256], display_arr [256,256]).
    """
    with rasterio.open(io.BytesIO(tif_bytes)) as src:
        vv = src.read(1).astype(np.float32)  # (H, W) in dB, e.g. -25 to 0

    vv = cv2.resize(vv, (256, 256), interpolation=cv2.INTER_LINEAR)

    # ── Debug: verify real SAR data is coming through ──
    print(f"  SAR VV  min={vv.min():.2f}  max={vv.max():.2f}  mean={vv.mean():.2f}")

    # ── Display array for visualization: normalize [-25, 0] → [0, 1] ──
    display_arr = (np.clip(vv, -25, 0) + 25) / 25.0

    # ── Channel 0: normalized VV [-40, 10] → [0, 1] ──
    ch0 = (np.clip(vv, -40, 10) + 40) / 50.0

    # ── Channel 1: VH approximation (VH ≈ VV - 6dB empirically) ──
    vh_approx = vv - 6.0
    ch1 = (np.clip(vh_approx, -45, -5) + 45) / 40.0

    # ── Channel 2: VH/VV ratio in linear scale ──
    vv_lin = np.power(10.0, np.clip(vv, -40, 0) / 10.0)
    vh_lin = np.power(10.0, np.clip(vh_approx, -45, -5) / 10.0)
    ratio  = np.clip(vh_lin / (vv_lin + 1e-8), 0.0, 2.0) / 2.0

    img_norm = np.stack([ch0, ch1, ratio], axis=-1).astype(np.float32)  # (256,256,3)

    print(f"  ch0={ch0.mean():.3f}  ch1={ch1.mean():.3f}  ratio={ratio.mean():.3f}")

    transform = A.Compose([ToTensorV2()])
    tensor = transform(image=img_norm)["image"].unsqueeze(0)  # (1, 3, 256, 256)

    return tensor, display_arr


def render_unet_overlay(display_arr, pred_mask):
    """
    Create one combined image: SAR grayscale + blue flood mask overlay.
    Works with any dimensions (256, 512, etc.)
    """
    h, w = display_arr.shape
    
    # Standardize SAR to uint8 RGB
    sar_uint8 = (np.clip(display_arr, 0, 1) * 255).astype(np.uint8)
    sar_rgb = np.stack([sar_uint8, sar_uint8, sar_uint8], axis=-1)

    blue = np.array([26, 95, 212], dtype=np.float32)
    out = sar_rgb.astype(np.float32)
    mask = pred_mask.astype(bool)

    # Alpha blend: flood pixels get blue overlay
    alpha = 0.65
    out[mask] = (1 - alpha) * out[mask] + alpha * blue

    return out.astype(np.uint8)


    
def render_sar_gray(display_arr):
    """Render the preprocessed SAR grayscale."""
    sar_uint8 = (np.clip(display_arr, 0, 1) * 255).astype(np.uint8)
    return sar_uint8


def render_prob_heatmap(pred_prob):
    """Render probability heatmap as an RGB image (0..1 -> blue-red)."""
    prob = np.clip(pred_prob, 0, 1)
    img = (prob * 255).astype(np.uint8)
    # Use a fixed colormap for readability
    color = cv2.applyColorMap(img, cv2.COLORMAP_JET)  # BGR
    return cv2.cvtColor(color, cv2.COLOR_BGR2RGB)


def render_unet_one_diagram(display_arr, pred_prob, pred_mask):
    """
    One combined diagram (dynamic sizing):
    - background: SAR grayscale
    - color: probability heatmap
    - highlight: predicted flood mask (blue overlay)
    """
    sar_gray = render_sar_gray(display_arr)
    sar_rgb = np.stack([sar_gray, sar_gray, sar_gray], axis=-1).astype(np.float32)

    prob = np.clip(pred_prob, 0, 1)
    prob_u8 = (prob * 255).astype(np.uint8)
    prob_color = cv2.applyColorMap(prob_u8, cv2.COLORMAP_JET)  # BGR
    prob_rgb = cv2.cvtColor(prob_color, cv2.COLOR_BGR2RGB).astype(np.float32)

    # Blend SAR + probability for context
    base = 0.45 * sar_rgb + 0.55 * prob_rgb

    # Highlight flood mask strongly
    mask = pred_mask.astype(bool)
    blue = np.array([26, 95, 212], dtype=np.float32)
    alpha = 0.70
    base[mask] = (1 - alpha) * base[mask] + alpha * blue

    return np.clip(base, 0, 255).astype(np.uint8)


@st.cache_resource
def load_model_cached():
    weights_path = resolve_weights_path()
    return load_flood_model(weights_path)


@st.cache_resource
def load_districts_cached():
    gdf = gpd.read_file(SHAPEFILE)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    name_col = detect_name_column(gdf)
    gdf = gdf.copy()
    gdf["__district_name__"] = gdf[name_col].astype(str)
    return gdf[["__district_name__", "geometry"]], name_col


def match_station_to_district(district_name: str, river_flows: list[dict]):
    dn = district_name.lower().strip()
    # Prefer direct inclusion matches both ways.
    for row in river_flows:
        st_name = (row.get("station") or "").lower()
        if dn in st_name or st_name in dn:
            return row
    return None

def fetch_current_sar_image(bbox, date_start, date_end, size=256):
    if isinstance(date_start, str):
        date_start = datetime.strptime(date_start, "%Y-%m-%d")
    if isinstance(date_end, str):
        date_end = datetime.strptime(date_end, "%Y-%m-%d")

    region = ee.Geometry.Rectangle(bbox)

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(date_start.strftime("%Y-%m-%d"), date_end.strftime("%Y-%m-%d"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )

    if collection.size().getInfo() == 0:
        st.warning("No SAR data in selected range, falling back to 2024.")
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region)
            .filterDate("2024-01-01", "2024-12-31")
            .select("VV")
        )

    image = collection.median()
    elevation = ee.Image("USGS/SRTMGL1_003")
    slope_mask = ee.Terrain.slope(elevation).lt(15)
    masked_image = image.updateMask(slope_mask).unmask(0)

    # ✅ GeoTIFF — rasterio can read this properly
    url = masked_image.getDownloadURL({
        "region": bbox,
        "dimensions": size,
        "format": "GEO_TIFF",
        "bands": ["VV"],
    })

    res = requests.get(url, timeout=120)
    res.raise_for_status()

    print(f"  GeoTIFF downloaded: {len(res.content)} bytes")
    return res.content  # raw GeoTIFF bytes

def fetch_2010_mask_image(mask_ee, bbox, size=256):
    """
    Fetches the 2010 binary mask as a PNG for visual comparison.
    """
    # mask_ee is 0 or 1. We'll visualize it as Blue.
    vis_img = mask_ee.visualize(palette=["black", "blue"], min=0, max=1)
    
    url = vis_img.getDownloadURL({
        "region": bbox,
        "dimensions": size,
        "format": "png",
    })
    
    res = requests.get(url, timeout=60)
    res.raise_for_status()
    return res.content

def main():
    st.title("FloodSense-PK: Unified Flood Dashboard (UNet + 2010 + FFC + Groq)")

    if "gee_inited" not in st.session_state:
        st.session_state["gee_inited"] = init_gee()

    gdf, _ = load_districts_cached()

    # Scale selector
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Analysis Scale")
    analysis_scale = st.sidebar.selectbox(
        "Select Scope", 
        ["District", "Province", "National"],
        help="National/Province will provide a Low-Res Overview of the entire region."
    )

    if analysis_scale == "National":
        district = "Pakistan"
    elif analysis_scale == "Province":
        prov_opts = sorted(["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Azad Jammu & Kashmir", "Gilgit-Baltistan"])
        district = st.sidebar.selectbox("Select Province", prov_opts)
    else:
        # District picker
        priority_only = st.sidebar.checkbox("Use Priority Districts only", value=True)
        if priority_only:
            opts = sorted(
                {x for x in gdf["__district_name__"].tolist() if any(p.lower() in x.lower() for p in PRIORITY_DISTRICTS)}
            )
        else:
            opts = sorted({x for x in gdf["__district_name__"].tolist()})
        district = st.sidebar.selectbox("District (Pre-defined)", options=opts, index=0 if opts else 0)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Advanced: Search Custom Area")
    search_name = st.sidebar.text_input("Enter Area Name (Overrides Scale)", help="Type a city or tehsil name. If found, it will override the scale selection.")

    # Date range
    default_end = datetime.now().date()
    default_start = default_end - timedelta(days=30)
    start_date = st.sidebar.date_input("Current SAR start date", value=default_start)
    end_date = st.sidebar.date_input("Current SAR end date", value=default_end)

    # Actions
    with st.sidebar:
        st.markdown("### Run")
        run = st.button("Run analysis", type="primary", use_container_width=True)

    if not run:
        st.info("Select a scale/district and press Run analysis.")
        return

    # ── Geometry Resolution ──
    geom = None
    display_name = district
    
    if search_name.strip():
        with st.spinner(f"Searching for '{search_name}' in Pakistan (Districts/Tehsils)..."):
            # Use FAO GAUL Level 2, filtered specifically for Pakistan
            pakistan_fc = ee.FeatureCollection("FAO/GAUL/2015/level2") \
                            .filter(ee.Filter.eq("ADM0_NAME", "Pakistan"))
            
            search_term = search_name.strip()
            # 1. Try exact match in ADM2_NAME (Districts/Sub-districts)
            match = pakistan_fc.filter(ee.Filter.eq("ADM2_NAME", search_term.capitalize()))
            
            # 2. Try partial match if exact fails
            if match.size().getInfo() == 0:
                match = pakistan_fc.filter(ee.Filter.stringContains("ADM2_NAME", search_term))
            
            # 3. Last fallback: search for Provinces/Regions
            if match.size().getInfo() == 0:
                prov_fc = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", "Pakistan"))
                match = prov_fc.filter(ee.Filter.stringContains("ADM1_NAME", search_term))

            if match.size().getInfo() > 0:
                feat = match.first()
                props = feat.toDictionary().getInfo()
                # Get the official administrative name (Tehsil/District)
                official_name = props.get("ADM2_NAME") or props.get("ADM1_NAME") or search_term
                
                geom = shape(feat.geometry().getInfo())
                display_name = f"{official_name} (Search)"
                st.sidebar.success(f"Verified Area: {official_name}")
            else:
                st.sidebar.warning(f"'{search_name}' not found. Using selection instead.")
    
    if geom is None:
        if analysis_scale == "National":
            # Pakistan full boundary
            country = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Pakistan"))
            geom = shape(country.first().geometry().getInfo())
            display_name = "Pakistan (National)"
        elif analysis_scale == "Province":
            # FAO Level 1 for provinces
            prov_fc = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", "Pakistan"))
            match = prov_fc.filter(ee.Filter.eq("ADM1_NAME", district))
            geom = shape(match.first().geometry().getInfo())
            display_name = f"{district} (Province)"
        else:
            row = gdf[gdf["__district_name__"] == district].iloc[0]
            geom = row["geometry"]

    ee_geom = shapely_to_ee(geom)
    district = display_name
    
    # Calculate bbox
    minx, miny, maxx, maxy = geom.bounds
    w_deg = maxx - minx
    h_deg = maxy - miny
    buffer_percent = 0.05 if analysis_scale in ["Province", "National"] else 0.15
    bbox = [
        minx - w_deg * buffer_percent, 
        miny - h_deg * buffer_percent, 
        maxx + w_deg * buffer_percent, 
        maxy + h_deg * buffer_percent
    ]
    
    # ── Dynamic Resolution Calculation ──
    # Target resolution: ~1000m for National/Province, ~80m for District
    target_res_m = 1000 if analysis_scale in ["Province", "National"] else 80
    
    pixels_w = int((w_deg * 1.1) * 111000 / target_res_m)
    pixels_h = int((h_deg * 1.1) * 111000 / target_res_m)
    
    # GEE Limits: 1024 is safe for memory and speed
    final_size = max(256, min(1024, max(pixels_w, pixels_h)))

    # 1) Historical 2010 mask
    if "hist_flood_mask" not in st.session_state:
        with st.spinner("Computing 2010 flood mask (Landsat via GEE)..."):
            pakistan_bbox = ee.Geometry.BBox(60.0, 23.0, 77.5, 37.5)
            hist_flood_mask, _, _ = get_flood_mask(pakistan_bbox)
            st.session_state["hist_flood_mask"] = hist_flood_mask

    with st.spinner("Computing 2010 flood %..."):
        pct_2010 = flood_percent_for_district(ee_geom, st.session_state["hist_flood_mask"])

    # 2) Current (Sentinel-1 + U-Net)
    model = load_model_cached()
    with st.spinner(f"Fetching Sentinel-1 SAR ({final_size}px)..."):
        sar_bytes = fetch_current_sar_image(
            bbox=bbox,
            date_start=str(start_date),
            date_end=str(end_date),
            size=final_size
        )

    with st.spinner("Running Tiled UNet analysis..."):
        unet_result = predict_flood(model, sar_bytes, district, bbox)

    pct_current = unet_result["water_coverage_pct"]
    risk_score = unet_result["risk_score"]
    settlement_risk = unet_result["settlement_risk"]

    # 3) River flows (FFC)
    @st.cache_data(ttl=300)
    def get_river_flows_cached():
        return get_ffc_data()

    with st.spinner("Scraping FFC river discharge data..."):
        river_flows = get_river_flows_cached()

    df_flows = pd.DataFrame(river_flows)
    matched_station = match_station_to_district(district, river_flows)

    # 4) Groq AI insights
    with st.spinner("Generating AI strategic insights..."):
        ai = FloodAI()
        summary_for_ai = [
            {
                "district": district,
                "flood_pct_current": pct_current,
                "flood_pct_2010": pct_2010,
                "risk_score": risk_score,
                "river_status": matched_station["status"] if matched_station else "UNKNOWN",
                "settlement_risk": settlement_risk,
            }
        ]
        insights = ai.generate_insights(summary_for_ai, river_flows)

    # 5) Visuals
    sar_gray = render_sar_gray(unet_result["display_arr"])
    overlay_img = render_unet_overlay(unet_result["display_arr"], unet_result["pred_mask"])
    prob_heatmap = render_prob_heatmap(unet_result["pred_prob"])

    with st.spinner("Aligning 2010 historical visuals..."):
        hist_mask_bytes = fetch_2010_mask_image(
            st.session_state["hist_flood_mask"],
            bbox=bbox,
            size=final_size
        )

    st.divider()

    # Clean, non-overlapping UI using tabs
    t1, t2, t3, t4 = st.tabs(["Overview", "Detection", "River Flows", "AI Insights"])


    with t1:
        st.subheader("Flood Severity Comparison: 2010 vs. Current")
        st.markdown("""
        Comparison between the historical maximum flood extent (2010) and the current situation detected by AI. 
        Blue areas indicate standing water.
        """)
        
        # Standardized height for professional alignment
        IMG_HEIGHT = 450
        
        # ── Visual Comparison Section ──
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            st.markdown("#### **[A] 2010 Historical Baseline**")
            st.image(hist_mask_bytes, caption="Satellite: Landsat-5 | Method: MNDWI", use_container_width=True)
            st.info("2010 Context: This represents the peak flood footprint during the 2010 disaster in Pakistan.")
        with col_img2:
            st.markdown(f"#### **[B] Current Situation ({start_date})**")
            st.image(overlay_img, caption="Satellite: Sentinel-1 SAR | Method: UNet AI", use_container_width=True)
            st.info("Live Status: Current water detection based on latest available radar imagery.")

        st.divider()

        # ── Metrics Section ──
        st.subheader("Statistical Analysis")
        c1, c2, c3 = st.columns(3)
        
        c1.metric(
            "2010 HISTORICAL %", 
            f"{pct_2010:.2f}%",
            help="Percentage of the district area flooded during the peak of the 2010 disaster."
        )
        c2.metric(
            "CURRENT FLOOD %", 
            f"{pct_current:.2f}%",
            help="Current percentage of the district area identified as flooded by the UNet AI model."
        )
        
        delta = None
        try:
            delta = float(pct_current) - float(pct_2010)
        except Exception:
            delta = None
            
        if delta is not None:
            c3.metric(
                "DELTA SEVERITY", 
                f"{delta:+.2f}%", 
                delta=f"{delta:+.2f}%", 
                delta_color="inverse",
                help="The difference in flood extent (Current % - 2010 %). A negative value indicates the current flood is less severe than 2010."
            )

        st.markdown(f"""
        ### **Executive Summary**
        *   **Extent:** The current flood extent is **{pct_current:.2f}%**, which is **{abs(delta):.2f}% {'higher' if delta > 0 else 'lower'}** than the 2010 benchmark.
        *   **Scale:** Current flooding is roughly **{ (pct_current / (pct_2010 if pct_2010 > 0 else 1)) * 100:.1f}%** as severe as the 2010 disaster.
        *   **Impact Level:** The system has classified this district as **{settlement_risk.upper()}** risk.
        """)
        
        st.progress(min(1.0, risk_score / 10.0))

        st.divider()

        st.markdown("### Local River Monitoring")
        if matched_station:
            st.success(
                f"**Station:** {matched_station['station']} | **River:** {matched_station['river']} | **Status:** {matched_station['status']}"
            )
            st.caption(
                f"Real-time Discharge (Cusecs) → Inflow: {matched_station.get('inflow')} | Outflow: {matched_station.get('outflow')}"
            )
        else:
            st.info("No monitoring station directly associated with this district name.")

    with t2:
        st.subheader("UNet Deep Learning Analysis")
        st.caption("Detailed breakdown of AI model outputs and confidence levels.")

        col_a, col_b = st.columns(2)
        
        # Ensure consistent sizing in detection tab as well
        with col_a:
            st.markdown("#### **Unified Detection Mask**")
            one_diagram = render_unet_one_diagram(
                unet_result["display_arr"], unet_result["pred_prob"], unet_result["pred_mask"]
            )
            st.image(one_diagram, caption="Background: SAR | Red-Yellow: Prob | Blue: Mask", use_container_width=True)
        
        with col_b:
            st.markdown("#### **Confidence Heatmap**")
            st.image(prob_heatmap, caption="Probability Score (0.0 to 1.0)", use_container_width=True)

        st.divider()
        st.markdown("### Model Performance Metrics")
        m1, m2, m3 = st.columns(3)
        m1.metric("Pixel Water Coverage", f"{pct_current:.2f}%")
        m2.metric("Total Affected Area", f"{unet_result['affected_area_km2']:.1f} km²")
        m3.metric("AI Architecture", "ResNet34-UNet")

    with t3:
        st.subheader("FFC river discharge (scraped)")
        if df_flows.empty:
            st.warning("No river flows found. Check `Data_URL` in `.env`.")
        else:
            # Status chips
            status_counts = df_flows["status"].value_counts(dropna=False).to_dict()
            st.write("### Status distribution")
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("NORMAL", status_counts.get("NORMAL", 0))
            sc2.metric("HIGH", status_counts.get("HIGH", 0))
            sc3.metric("EXTREME", status_counts.get("EXTREME", 0))
            sc4.metric("NOT RECEIVED", status_counts.get("NOT_RECEIVED", 0))

            # Charts: top inflow/outflow
            st.write("### Top stations by inflow/outflow")
            df_plot = df_flows.copy()
            df_plot["inflow"] = pd.to_numeric(df_plot["inflow"], errors="coerce")
            df_plot["outflow"] = pd.to_numeric(df_plot["outflow"], errors="coerce")

            top_in = df_plot.dropna(subset=["inflow"]).sort_values("inflow", ascending=False).head(10)
            top_out = df_plot.dropna(subset=["outflow"]).sort_values("outflow", ascending=False).head(10)

            if len(top_in) > 0:
                st.bar_chart(top_in.set_index("station")["inflow"], use_container_width=True)
            if len(top_out) > 0:
                st.bar_chart(top_out.set_index("station")["outflow"], use_container_width=True)

            st.write("### Inflow vs outflow (all stations)")
            df_sc = df_plot.dropna(subset=["inflow", "outflow"]).copy()
            if len(df_sc) > 0:
                fig, ax = plt.subplots(figsize=(8, 4))
                # Color by status for quick reading
                colors = {"NORMAL": "#00cc66", "HIGH": "#ffaa00", "EXTREME": "#ff4444", "NOT_RECEIVED": "#7b8794", "UNKNOWN": "#8aa5ff"}
                for status, g in df_sc.groupby(df_sc["status"].astype(str)):
                    ax.scatter(g["inflow"], g["outflow"], s=28, alpha=0.75, label=status, color=colors.get(status, "#8aa5ff"))
                ax.set_xlabel("Inflow")
                ax.set_ylabel("Outflow")
                ax.legend(fontsize=8, loc="best")
                ax.grid(True, alpha=0.2)
                st.pyplot(fig)

            # Full table
            st.dataframe(df_flows, use_container_width=True, height=420)

    with t4:
        st.subheader("Groq AI strategic insights")
        st.caption("Generated using Current vs 2010 flood context + live river discharge.")
        provider = "Groq" if os.getenv("GROQ_API_KEY") else "Gemini/Simulated"
        st.info(f"AI provider: {provider}")
        st.markdown(insights)


if __name__ == "__main__":
    main()

