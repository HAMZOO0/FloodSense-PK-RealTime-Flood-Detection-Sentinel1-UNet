"""Full district flood analysis.

Pipeline per district (same flow as the Streamlit dashboard / Flet app):
    1. GEE init + district geometry
    2. Live FFD river data + station matching
    3. 2010 Landsat baseline flood % (historical benchmark)
    4. Sentinel-1 SAR tile (last N days) → tiled U-Net inference
    5. Defensible weighted risk score (FloodAI formula)
    6. Persist the result to MongoDB (analyses) + auto-alert when risky

This is slow (GEE + torch, tens of seconds) — call it through the background
job runner, never directly from a request handler.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db import require_db, serialize
from ..errors import not_found, service_unavailable
from . import geodata, rivers
from .gee import init_gee
from .model import get_model

logger = logging.getLogger("floodsense.analysis")


# ── GEE SAR fetch ───────────────────────────────────────────────────────────
def fetch_current_sar_image(bbox, date_start, date_end, size: int = 512) -> bytes:
    """Download a slope-masked Sentinel-1 VV GeoTIFF for the bbox from GEE."""
    import ee
    import requests

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
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region)
            .filterDate("2024-01-01", "2024-12-31")
            .select("VV")
        )
        if collection.size().getInfo() == 0:
            raise not_found(
                "NO_SAR_IMAGERY",
                "No Sentinel-1 imagery is available for this district/date range.",
            )

    image = collection.median()
    elevation = ee.Image("USGS/SRTMGL1_003")
    slope_mask = ee.Terrain.slope(elevation).lt(15)
    masked_image = image.updateMask(slope_mask).unmask(0)

    url = masked_image.getDownloadURL(
        {"region": bbox, "dimensions": size, "format": "GEO_TIFF", "bands": ["VV"]}
    )
    res = requests.get(url, timeout=300)
    res.raise_for_status()
    return res.content


def flood_overlay_png_base64(display_arr, pred_mask) -> str:
    """SAR backdrop with the U-Net flood mask blended in blue, as base64 PNG."""
    import cv2
    import numpy as np

    sar_uint8 = (np.clip(display_arr, 0, 1) * 255).astype(np.uint8)
    sar_rgb = np.stack([sar_uint8, sar_uint8, sar_uint8], axis=-1)

    blue = np.array([26, 95, 212], dtype=np.float32)
    out = sar_rgb.astype(np.float32)
    mask = pred_mask.astype(bool)
    alpha = 0.65
    out[mask] = (1 - alpha) * out[mask] + alpha * blue
    out = out.astype(np.uint8)

    ok, buffer = cv2.imencode(".png", cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    if not ok:
        raise service_unavailable("IMAGE_ENCODE_FAILED", "Could not encode flood map PNG.")
    return base64.b64encode(buffer).decode("utf-8")


def _risk_level(score: float) -> str:
    if score >= 7:
        return "HIGH RISK"
    if score >= 4:
        return "MODERATE RISK"
    return "LOW RISK"


# ── Main entry point (run inside a background job) ──────────────────────────
def run_district_analysis(district: str, job_id: str | None = None) -> dict:
    """Run the full analysis and return the stored, JSON-safe document."""
    init_gee()

    actual_name, geom, bbox = geodata.find_district(district)
    logger.info("[analysis] %s — starting full analysis", actual_name)

    # River data (best-effort: analysis proceeds without a matched gauge)
    matched_station = None
    try:
        river_payload = rivers.get_river_data()
        matched_station = rivers.match_station_to_district(
            actual_name, river_payload["stations"]
        )
        river_stations = river_payload["stations"]
    except Exception as e:
        logger.warning("[analysis] river data unavailable: %s", e)
        river_stations = []

    # Historical 2010 baseline (Landsat MNDWI)
    from utils.districts import flood_percent_for_district, shapely_to_ee
    from utils.ndwi import get_flood_mask

    ee_geom = shapely_to_ee(geom)
    try:
        hist_mask, _, _ = get_flood_mask(ee_geom)
        pct_2010 = float(flood_percent_for_district(ee_geom, hist_mask))
    except Exception as e:
        logger.warning("[analysis] 2010 baseline failed: %s", e)
        pct_2010 = 0.0

    # Current flood extent — Sentinel-1 SAR + tiled U-Net
    date_end = datetime.now()
    date_start = date_end - timedelta(days=settings.SAR_LOOKBACK_DAYS)
    sar_bytes = fetch_current_sar_image(
        bbox, date_start, date_end, size=settings.SAR_IMAGE_SIZE
    )

    from models.model_inference import predict_flood

    model = get_model()
    unet = predict_flood(model, sar_bytes, actual_name, bbox)
    pct_current = float(unet["water_coverage_pct"])

    map_image = flood_overlay_png_base64(unet["display_arr"], unet["pred_mask"])

    # Defensible weighted risk score (flood extent 40% / 2010 delta 30% / hydraulics 30%)
    from .ai import get_flood_ai

    risk_input = {
        "district": actual_name,
        "flood_pct_current": pct_current,
        "flood_pct_2010": pct_2010,
        "river_status": matched_station["status"] if matched_station else "UNKNOWN",
    }
    risk_score = float(
        get_flood_ai().calculate_defensible_risk(risk_input, river_stations)
    )

    doc = {
        "district": actual_name,
        "requested_district": district,
        "job_id": job_id,
        "risk_score": risk_score,
        "risk_level": _risk_level(risk_score),
        "flood_pct_current": round(pct_current, 2),
        "flood_pct_2010": round(pct_2010, 2),
        "delta_vs_2010": round(pct_current - pct_2010, 2),
        "affected_area_km2": float(unet["affected_area_km2"]),
        "flood_pixels": int(unet["flood_pixels"]),
        "settlement_risk": unet["settlement_risk"],
        "confidence": unet["confidence"],
        "model_used": unet["model_used"],
        "sar_window": {
            "start": date_start.strftime("%Y-%m-%d"),
            "end": date_end.strftime("%Y-%m-%d"),
            "size_px": settings.SAR_IMAGE_SIZE,
        },
        "bbox": bbox,
        "river": matched_station,
        "map_image_base64": map_image,
        "created_at": datetime.now(timezone.utc),
    }

    db = require_db()
    db.analyses.insert_one(doc)
    logger.info(
        "[analysis] %s — done (risk %.1f/10, %.2f%% flooded)",
        actual_name,
        risk_score,
        pct_current,
    )

    _maybe_create_auto_alert(db, doc)
    return serialize(doc, exclude=("map_image_base64",))


def _maybe_create_auto_alert(db, analysis: dict) -> None:
    """Create an alert document when the analysis risk crosses the threshold."""
    try:
        if analysis["risk_score"] < settings.ALERT_RISK_THRESHOLD:
            return
        severity = "HIGH" if analysis["risk_score"] >= 7 else "MODERATE"
        db.alerts.insert_one(
            {
                "district": analysis["district"],
                "severity": severity,
                "risk_score": analysis["risk_score"],
                "message": (
                    f"{severity} flood risk in {analysis['district']}: "
                    f"{analysis['flood_pct_current']:.2f}% of the district is under water "
                    f"(2010 benchmark: {analysis['flood_pct_2010']:.2f}%). "
                    f"Risk score {analysis['risk_score']:.1f}/10."
                ),
                "source": "auto-analysis",
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception as e:
        logger.warning("Auto-alert creation failed: %s", e)


# ── Reads (used by routes) ──────────────────────────────────────────────────
def latest_analysis(district: str, include_image: bool = False) -> dict:
    actual_name, _, _ = geodata.find_district(district)
    db = require_db()
    doc = db.analyses.find_one({"district": actual_name}, sort=[("created_at", -1)])
    if doc is None:
        raise not_found(
            "ANALYSIS_NOT_FOUND",
            f"No analysis exists for '{actual_name}' yet. "
            f"Start one with POST /api/analysis/{actual_name}.",
        )
    exclude = () if include_image else ("map_image_base64",)
    return serialize(doc, exclude=exclude)


def latest_analysis_image_png(district: str) -> bytes:
    doc = latest_analysis(district, include_image=True)
    image_b64 = doc.get("map_image_base64")
    if not image_b64:
        raise not_found(
            "IMAGE_NOT_FOUND", f"The latest analysis for '{district}' has no map image."
        )
    return base64.b64decode(image_b64)


def latest_analyses_all(limit: int = 200) -> list[dict]:
    """Newest analysis per district (for national map / list views)."""
    db = require_db()
    docs = db.analyses.aggregate(
        [
            {"$sort": {"created_at": -1}},
            {"$group": {"_id": "$district", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$project": {"map_image_base64": 0}},
            {"$sort": {"risk_score": -1}},
            {"$limit": limit},
        ]
    )
    return [serialize(d) for d in docs]
