import ee
import requests
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image
import io
import json
import os
from dotenv import load_dotenv
from model_inference import load_flood_model, predict_flood

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")

DISTRICTS = {
    "DG Khan":  [70.2, 29.8, 71.2, 30.8],
    "Sukkur":   [68.5, 27.5, 69.5, 28.5],
    "Nowshera": [71.8, 34.0, 72.4, 34.6],
    "Larkana":  [67.8, 27.3, 68.5, 27.9],
    "Quetta":   [66.8, 30.0, 67.8, 31.0],
}

# Load model ONCE at startup
FLOOD_MODEL = load_flood_model("models/best_model.pth")


# ══════════════════════════════════════════════════════════
# STEP 1 — Init Earth Engine
# ══════════════════════════════════════════════════════════
def init_ee():
    try:
        ee.Initialize(project=PROJECT_ID)
        print("Earth Engine connected!")
    except Exception as e:
        print(f"EE init failed: {e}")
        raise


# ══════════════════════════════════════════════════════════
# STEP 2 — Fetch SAR image from Google Earth Engine
# ══════════════════════════════════════════════════════════
def fetch_sar_tile(bbox, date_start, date_end, size=256):
    print(f"  Fetching SAR image from Google Earth Engine...")
    print(f"  Area  : {bbox}")
    print(f"  Dates : {date_start} → {date_end}")

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
    print(f"  Found {count} satellite scenes")

    if count == 0:
        print("  No images found — widening date range to full 2024...")
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region)
            .filterDate("2024-01-01", "2024-12-31")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .select("VV")
        )

    image = collection.median()

    # Download as PNG — GEE scales SAR dB values min=-25, max=0
    url = image.getThumbURL({
        "region":     bbox,
        "dimensions": size,
        "format":     "png",
        "min":        -25,
        "max":        0,
    })

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    print(f"  Image downloaded — {len(response.content):,} bytes")

    return response.content


# ══════════════════════════════════════════════════════════
# STEP 3 — Display result with U-Net flood mask
# ══════════════════════════════════════════════════════════
def display_with_model_mask(image_bytes, model_result, district_name):
    """
    Shows 3-panel visualization:
    Panel 1 — Raw SAR image from GEE
    Panel 2 — U-Net flood mask overlay (blue = flood)
    Panel 3 — Risk score bar chart
    """
    # Use the preprocessed display array from model_result
    # This is already correctly normalized and matches model input
    display_arr = model_result.get("display_arr")

    if display_arr is not None:
        # Resize display array to 256x256 for visualization
        from PIL import Image as PILImage
        disp = PILImage.fromarray((display_arr * 255).astype(np.uint8))
        disp = disp.resize((256, 256))
        arr  = np.array(disp)
    else:
        # Fallback — open original PNG
        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((256, 256))
        arr = np.array(img)

    mask = model_result["pred_mask"]   # 256x256 bool array

    # Build RGB overlay — blue where flood predicted
    rgb = np.stack([arr, arr, arr], axis=-1).copy()
    rgb[mask] = [30, 90, 210]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        f"FloodSense — {district_name}  |  "
        f"Risk: {model_result['risk_score']}/10  |  "
        f"{model_result['water_coverage_pct']}% flooded  |  "
        f"{model_result['affected_area_km2']} km²",
        fontsize=13, fontweight="bold"
    )

    # Panel 1 — Raw SAR
    axes[0].imshow(arr, cmap="gray")
    axes[0].set_title("SAR Image\n(Sentinel-1 via Google Earth Engine)")
    axes[0].axis("off")

    # Panel 2 — Flood overlay
    axes[1].imshow(rgb)
    axes[1].set_title(
        f"U-Net Flood Detection\n"
        f"{model_result['affected_area_km2']} km² affected"
    )
    axes[1].legend(
        handles=[
            mpatches.Patch(color=(30/255, 90/255, 210/255), label="Flood"),
            mpatches.Patch(color="gray", label="Land")
        ],
        loc="lower right", fontsize=9
    )
    axes[1].axis("off")

    # Panel 3 — Risk bar
    score     = model_result["risk_score"]
    bar_color = "#3B6D11" if score <= 3 else "#BA7517" if score <= 6 else "#A32D2D"

    # Background bar (full scale)
    axes[2].barh(["Risk"], [10],    color="#EEEEEE",  height=0.4, zorder=0)
    # Actual risk bar
    axes[2].barh(["Risk"], [score], color=bar_color,  height=0.4, zorder=1)
    axes[2].set_xlim(0, 12)
    axes[2].set_title("Flood Risk Score\n(U-Net ResNet34 — IoU: 0.9894)")
    axes[2].set_xlabel("1 = safe,  10 = severe")
    axes[2].text(
        score + 0.3, 0, f"{score}/10",
        va="center", fontsize=13, fontweight="bold", color=bar_color
    )

    plt.tight_layout()
    fname = f"floodsense_{district_name.lower().replace(' ', '_')}.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved → {fname}")
    plt.show()
    plt.close()


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def run(
        district_name="Quetta",
        date_start="2024-08-01",
        date_end="2024-08-15"
):
    print(f"\n{'='*55}")
    print(f"  FloodSense — {district_name}")
    print(f"{'='*55}\n")

    # 1. Connect to Earth Engine
    init_ee()

    bbox = DISTRICTS[district_name]

    # 2. Download SAR satellite image from GEE
    image_bytes = fetch_sar_tile(bbox, date_start, date_end)

    # 3. Run U-Net flood segmentation
    print("  Running U-Net flood segmentation...")
    model_result = predict_flood(FLOOD_MODEL, image_bytes, district_name, bbox)

    print(f"\n  Results for {district_name}:")
    print(f"  Water coverage : {model_result['water_coverage_pct']}%")
    print(f"  Affected area  : {model_result['affected_area_km2']} km²")
    print(f"  Risk score     : {model_result['risk_score']}/10")
    print(f"  Risk level     : {model_result['settlement_risk']}")

    # 4. Show visualization
    display_with_model_mask(image_bytes, model_result, district_name)

    # 5. Save JSON result
    output = {
        "district":   district_name,
        "date_range": f"{date_start} to {date_end}",
        "risk_score": model_result["risk_score"],
        "water_pct":  model_result["water_coverage_pct"],
        "area_km2":   model_result["affected_area_km2"],
        "risk_level": model_result["settlement_risk"],
    }

    out_file = f"result_{district_name.lower().replace(' ', '_')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Result saved → {out_file}")

    return output


if __name__ == "__main__":
    run(
        district_name="Quetta",
        date_start="2024-08-01",
        date_end="2024-08-15",
    )
