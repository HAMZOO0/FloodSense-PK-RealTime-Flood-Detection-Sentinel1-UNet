import ee
import requests
import base64
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image # use to open the image in mmeory  
import io
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()
# ══════════════════════════════════════════════════════════
# CONFIG — change your project ID here
# ══════════════════════════════════════════════════════════
PROJECT_ID = os.getenv("PROJECT_ID")

# Pakistan districts bounding boxes [min_lon, min_lat, max_lon, max_lat]
DISTRICTS = {
    "DG Khan":  [70.2, 29.8, 71.2, 30.8],
    "Sukkur":   [68.5, 27.5, 69.5, 28.5],
    "Nowshera": [71.8, 34.0, 72.4, 34.6],
    "Larkana":  [67.8, 27.3, 68.5, 27.9],
}


# ══════════════════════════════════════════════════════════
# STEP 1 — Initialize Earth Engine
# ══════════════════════════════════════════════════════════
def init_ee():
    try:
        ee.Initialize(project=PROJECT_ID)
        print("✅ Earth Engine connected!")
    except Exception as e:
        print(f"❌ EE init failed: {e}")
        print("Run 'earthengine authenticate' in terminal first.")
        raise


# ══════════════════════════════════════════════════════════
# STEP 2 — Fetch SAR satellite tile from GEE
# ══════════════════════════════════════════════════════════
def fetch_sar_tile(bbox, date_start, date_end, size=256):
    """
    Fetch Sentinel-1 SAR tile for a bounding box and date range.
    Returns raw PNG bytes.
    """
    print(f"   Fetching SAR imagery {date_start} → {date_end} ...")

    region = ee.Geometry.Rectangle(bbox)

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(date_start, date_end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )

    count = collection.size().getInfo()
    print(f"   Found {count} SAR scenes")

    if count == 0:
        print("    No imagery found — widening date range by 30 days")
        # Try wider range
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region)
            .filterDate("2024-01-01", "2024-12-31")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .select("VV")
        )
        count = collection.size().getInfo()
        print(f"  📸 Found {count} scenes in wider range")

    image = collection.median()  # median composite — reduces noise

    # Build thumbnail URL
    url = image.getThumbURL({
        "region":     bbox,
        "dimensions": size,
        "format":     "png",
        "min":        -25,   # SAR VV range in dB
        "max":        0,
    })

    print(f"   Downloading tile...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    print(f"   Tile downloaded — {len(response.content)} bytes")
    return response.content


# ══════════════════════════════════════════════════════════
# STEP 3 — Analyze water coverage from SAR pixel values
# ══════════════════════════════════════════════════════════
def analyze_water(image_bytes, water_threshold=60):
    """
    In SAR imagery: water = very dark (low backscatter).
    Pixels below threshold are classified as water.
    Returns dict with stats.
    """
    img  = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
    arr  = np.array(img, dtype=np.float32)

    total_pixels = arr.size
    water_pixels = np.sum(arr < water_threshold)
    water_pct    = (water_pixels / total_pixels) * 100

    # Simple risk score: 0–100% water → 1–10 score
    risk_score = min(10, max(1, round(water_pct / 10) + 1))

    return {
        "water_pct":     round(water_pct, 2),
        "water_pixels":  int(water_pixels),
        "total_pixels":  int(total_pixels),
        "mean_backscatter": round(float(np.mean(arr)), 2),
        "min_backscatter":  round(float(np.min(arr)), 2),
        "risk_score":    risk_score,
    }


# ══════════════════════════════════════════════════════════
# STEP 4 — Display the tile visually
# ══════════════════════════════════════════════════════════
def display_tile(image_bytes, district_name, stats):
    """
    Show 3-panel figure:
    Left  — raw grayscale SAR
    Middle — water mask (blue = water, green = land)
    Right  — risk score bar
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    arr = np.array(img, dtype=np.float32)

    # Build water mask RGB
    water_mask = arr < 60
    rgb = np.zeros((*arr.shape, 3), dtype=np.uint8)
    rgb[~water_mask] = [120, 160, 90]   # green = land
    rgb[water_mask]  = [30,  90,  210]  # blue  = water

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle(
        f"FloodSense — {district_name}  |  Risk Score: {stats['risk_score']}/10",
        fontsize=14, fontweight="bold", color="#0D2B4E"
    )

    # Panel 1 — raw SAR
    axes[0].imshow(arr, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title("Raw SAR (Sentinel-1 VV)", fontsize=11)
    axes[0].axis("off")

    # Panel 2 — water mask
    axes[1].imshow(rgb)
    axes[1].set_title(
        f"Water detection  ({stats['water_pct']}% coverage)",
        fontsize=11
    )
    axes[1].axis("off")
    land_patch  = mpatches.Patch(color="#789060", label="Land")
    water_patch = mpatches.Patch(color="#1E5AD2", label="Water")
    axes[1].legend(handles=[water_patch, land_patch], loc="lower right", fontsize=9)

    # Panel 3 — risk gauge
    score     = stats["risk_score"]
    bar_color = "#3B6D11" if score <= 3 else "#BA7517" if score <= 6 else "#A32D2D"
    axes[2].barh(["Risk"], [score], color=bar_color, height=0.4)
    axes[2].barh(["Risk"], [10],    color="#EEEEEE",  height=0.4, zorder=0)
    axes[2].set_xlim(0, 10)
    axes[2].set_title("Flood Risk Score", fontsize=11)
    axes[2].set_xlabel("Score (1 = safe, 10 = severe)")
    axes[2].text(
        score + 0.2, 0, f"{score}/10",
        va="center", fontsize=13, fontweight="bold", color=bar_color
    )

    plt.tight_layout()

    # Save to file
    filename = f"floodsense_{district_name.lower().replace(' ', '_')}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"    Visualization saved → {filename}")
    plt.show()


# ══════════════════════════════════════════════════════════
# STEP 5 — Build Gemini-ready payload
# ══════════════════════════════════════════════════════════
def build_gemini_payload(tile_b64, district_name, bbox, stats,
                          river_level_m=None, rainfall_48h_mm=None):
    """
    Returns a dict ready to POST to the Gemini API.
    """
    context = f"""
District: {district_name} (Pakistan)
Season: Monsoon analysis
Bounding box: {bbox}
Pre-computed water coverage: {stats['water_pct']}%
Mean SAR backscatter: {stats['mean_backscatter']} (lower = more water)
Local risk estimate: {stats['risk_score']}/10
River level: {river_level_m or 'N/A'} m
Rainfall last 48h: {rainfall_48h_mm or 'N/A'} mm
"""

    prompt = f"""{context}
Analyze this Sentinel-1 SAR satellite image of {district_name}, Pakistan.
SAR images show water as DARK areas and land as LIGHTER areas.

Return ONLY valid JSON, no markdown, exactly this schema:
{{
  "risk_score": <1-10 integer>,
  "water_coverage_pct": <float>,
  "affected_area_km2": <float>,
  "water_extent_change": "increasing|stable|decreasing",
  "settlement_risk": "high|medium|low",
  "confidence": "high|medium|low",
  "visual_indicators": ["<observation 1>", "<observation 2>"],
  "urdu_advisory": "<2 sentence Urdu advisory>",
  "en_advisory": "<2 sentence English advisory>"
}}"""

    return {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": tile_b64
                    }
                },
                {"text": prompt}
            ]
        }],
        "generationConfig": {"temperature": 0.1}
    }


# ══════════════════════════════════════════════════════════
# STEP 6 — Send to Gemini and get risk analysis
# ══════════════════════════════════════════════════════════
def analyze_with_gemini(tile_b64, district_name, bbox, stats, gemini_api_key):
    """
    Calls Gemini Vision and returns parsed JSON risk assessment.
    """
    print(f"  🤖 Sending to Gemini Vision...")

    payload = build_gemini_payload(tile_b64, district_name, bbox, stats)
    url     = (
        f"{os.getenv('URL')}models/gemini-1.5-pro:generateContent?key={os.getenv('GEMINI_API_KEY')}"
    )

    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()

    raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]

    # Strip any accidental markdown fencing
    clean = raw_text.replace("```json", "").replace("```", "").strip()

    result = json.loads(clean)
    print(f"  ✅ Gemini risk score: {result['risk_score']}/10")
    print(f"  📢 Advisory: {result['en_advisory']}")
    return result


# ══════════════════════════════════════════════════════════
# MAIN — run for one or all districts
# ══════════════════════════════════════════════════════════
def run(district_name="DG Khan",
        date_start="2024-08-01",
        date_end="2024-08-15",
        gemini_api_key=None):   # paste your Gemini key here

    print(f"\n{'='*55}")
    print(f" FloodSense — Analyzing {district_name}")
    print(f"{'='*55}\n")

    # 1. Init EE
    init_ee()

    bbox = DISTRICTS[district_name]

    # 2. Fetch tile
    image_bytes = fetch_sar_tile(bbox, date_start, date_end)

    # 3. Local water analysis
    print("   Running local water analysis...")
    stats = analyze_water(image_bytes)
    print(f"   Water coverage: {stats['water_pct']}%")
    print(f"   Local risk estimate: {stats['risk_score']}/10")

    # 4. Display
    display_tile(image_bytes, district_name, stats)

    # 5. Base64 encode
    tile_b64 = base64.b64encode(image_bytes).decode("utf-8")
    print(f"  🔢 Base64 ready — {len(tile_b64)} chars")

    # 6. Gemini (optional — only runs if you provide an API key)
    gemini_result = None
    if gemini_api_key:
        gemini_result = analyze_with_gemini(
            tile_b64, district_name, bbox, stats, gemini_api_key
        )
    else:
        print("  ⏭️  Skipping Gemini (no API key provided)")
        print("      Get key at: aistudio.google.com/app/apikey")

    # 7. Save output JSON
    output = {
        "district":       district_name,
        "bbox":           bbox,
        "date_range":     f"{date_start} to {date_end}",
        "local_stats":    stats,
        "gemini_result":  gemini_result,
    }
    out_file = f"floodsense_{district_name.lower().replace(' ', '_')}_result.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n   Full result saved → {out_file}")
    print(f"\n{'='*55}\n")

    return output


# ══════════════════════════════════════════════════════════
# RUN IT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":

    result = run(
        district_name  = "DG Khan",      # change to any key in DISTRICTS
        date_start     = "2024-08-01",
        date_end       = "2024-08-15",
        gemini_api_key = None,           # paste your key from aistudio.google.com
    )