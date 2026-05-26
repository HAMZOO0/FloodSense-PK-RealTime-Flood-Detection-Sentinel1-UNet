"""
main.py
-------
Unified Flood Detection Engine for Pakistan.
Combines:
1. Live River Flows (FFC Scraper)
2. Historical 2010 Flood Analysis (GEE Landsat)
3. Current Run-time Flood Prediction (GEE Sentinel-1 + UNet)
4. AI Strategic Insights (Groq / Gemini)
"""

import os
import ee
import json
import pandas as pd
import requests
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Internal Imports
from scrapers.ffc_scraper import get_ffc_data
from engine.ai_alerts import FloodAI
from engine.data_manager import save_district_data, save_json
from models.model_inference import load_flood_model, predict_flood
from utils.ndwi import get_flood_mask
from utils.districts import detect_name_column, shapely_to_ee, PRIORITY_DISTRICTS
from utils.visualize import plot_static_map, plot_interactive_map
import geopandas as gpd

load_dotenv()

# ── CONFIG ──────────────────────────────────────────────────────────────────
SHAPEFILE = "pakistan_districts.json"
PROJECT_ID = os.getenv("PROJECT_ID")
WEIGHTS_PATH = os.path.abspath("models/best_model.pth")

def init_gee():
    print("🔐 Initializing Google Earth Engine...")
    try:
        if PROJECT_ID:
            ee.Initialize(project=PROJECT_ID)
        else:
            ee.Initialize()
        print("   ✅ GEE Connected.")
    except Exception as e:
        print(f"   ❌ GEE Initialization failed: {e}")
        return False
    return True

def fetch_current_sar_image(bbox, size=256):
    """
    Fetches latest Sentinel-1 SAR image with a Slope Mask to fix mountain false positives.
    """
    date_end = datetime.now()
    date_start = date_end - timedelta(days=30)
    
    region = ee.Geometry.Rectangle(bbox)
    
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(date_start.strftime('%Y-%m-%d'), date_end.strftime('%Y-%m-%d'))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )
    
    if collection.size().getInfo() == 0:
        # Fallback to longer range if no recent images
        collection = ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(region).filterDate("2024-01-01", "2024-12-31").select("VV")

    image = collection.median()
    
    # ── MOUNTAIN FIX: Slope Masking ──────────────────────────
    # Radar shadows on steep slopes look like water (dark). 
    # We mask areas with slope > 15 degrees.
    elevation = ee.Image("USGS/SRTMGL1_003")
    slope = ee.Terrain.slope(elevation)
    slope_mask = slope.lt(15) 
    
    # Unmask to 0 (which is white in our -25 to 0 scale) so masked areas are seen as LAND
    masked_image = image.updateMask(slope_mask).unmask(0)
    
    url = masked_image.getThumbURL({
        "region": bbox,
        "dimensions": size,
        "format": "png",
        "min": -25,
        "max": 0,
    })
    
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    return res.content

def main():
    if not init_gee(): return

    # 1. Load Resources
    print("\n🧠 Loading Models and AI...")
    model = load_flood_model(WEIGHTS_PATH)
    ai = FloodAI()
    
    print("\n🌊 Fetching Live River flows...")
    river_flows = get_ffc_data()
    save_json("river_flows.json", {"timestamp": datetime.now().strftime("%Y-%m-%d"), "data": river_flows})

    # 2. Load Districts
    print(f"\n📂 Processing Priority Districts from {SHAPEFILE}...")
    gdf = gpd.read_file(SHAPEFILE)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    name_col = detect_name_column(gdf)
    mask = gdf[name_col].apply(lambda x: any(p.lower() in str(x).lower() for p in PRIORITY_DISTRICTS))
    gdf_priority = gdf[mask].copy()
    print(f"   Targeting {len(gdf_priority)} districts.")

    # 3. Process each district
    results = []
    
    # Pre-fetch 2010 flood mask for whole Pakistan to save time (Historical Context)
    print("\n🛰  Computing 2010 Historical Flood Baseline (GEE Landsat)...")
    pakistan_bbox = ee.Geometry.BBox(60.0, 23.0, 77.5, 37.5)
    hist_flood_mask, _, _ = get_flood_mask(pakistan_bbox)

    for i, row in gdf_priority.iterrows():
        name = row[name_col]
        print(f"\n[{i+1}] Analyzing: {name}")
        
        try:
            ee_geom = shapely_to_ee(row.geometry)
            bbox = row.geometry.bounds # (minx, miny, maxx, maxy)
            
            # A. Historical 2010 Flood %
            # Reusing the function from districts.py logic (could import it but easier to keep here for clarity)
            from utils.districts import flood_percent_for_district
            pct_2010 = flood_percent_for_district(ee_geom, hist_flood_mask)
            
            # B. Current Flood Detection (UNet + Sentinel-1)
            print(f"   Running Live SAR Detection...")
            sar_bytes = fetch_current_sar_image(list(bbox))
            unet_result = predict_flood(model, sar_bytes, name, list(bbox))
            pct_current = unet_result['water_coverage_pct']
            
            # C. River Flow Match
            flow_status = "NORMAL"
            for f in river_flows:
                if f['station'].lower() in name.lower():
                    flow_status = f['status']
                    break
            
            results.append({
                "district": name,
                "flood_pct_2010": pct_2010,
                "flood_pct_current": pct_current,
                "river_status": flow_status,
                "risk_score": unet_result['risk_score'],
                "geometry": row.geometry
            })
            
            print(f"   Done: 2010({pct_2010}%) | Current({pct_current}%) | Flow({flow_status})")

        except Exception as e:
            print(f"   ⚠️ Error processing {name}: {e}")

    # 4. Generate AI Insights
    print("\n💡 Generating AI Insights (Groq/Gemini)...")
    summary_for_ai = [{k:v for k,v in r.items() if k != 'geometry'} for r in results]
    insights = ai.generate_insights(summary_for_ai, river_flows)
    save_json("ai_insights.json", {"content": insights})

    # 5. Export and Visualize
    print("\n📊 Creating Dashboard...")
    df_results = pd.DataFrame(results)
    
    # For visualization, we'll use current flood % as primary color
    df_results['flood_pct'] = df_results['flood_pct_current'] 
    
    os.makedirs("outputs", exist_ok=True)
    plot_static_map(df_results, out_path="outputs/flood_map.png")
    plot_interactive_map(df_results, out_path="outputs/dashboard.html")
    
    print("\n✅ All set! Dashboard ready at outputs/dashboard.html")

if __name__ == "__main__":
    main()
