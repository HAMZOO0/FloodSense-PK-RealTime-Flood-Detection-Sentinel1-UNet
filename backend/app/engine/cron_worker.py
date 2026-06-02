from __future__ import annotations

import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import ee
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, To
from supabase import Client, create_client
from twilio.rest import Client as TwilioClient

from app.engine.ai_alerts import FloodAI
from app.models.model_inference import load_flood_model, predict_flood
from app.scrapers.ffc_scraper import get_ffc_data

logger = logging.getLogger("floodsense.cron")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
PROJECT_ID = os.getenv("PROJECT_ID")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")

DISTRICT_BBOX_OVERRIDES = os.getenv("DISTRICT_BBOX_OVERRIDES", "{}")
ALERT_COOLDOWN_HOURS = 12
ALERT_STATE: Dict[Tuple[str, str], datetime] = {}

_supabase_client: Optional[Client] = None
_scheduler: Optional[BackgroundScheduler] = None
_model = None


def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_client


def get_twilio_client() -> Optional[TwilioClient]:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return None


def get_sendgrid_client() -> Optional[SendGridAPIClient]:
    if SENDGRID_API_KEY:
        return SendGridAPIClient(api_key=SENDGRID_API_KEY)
    return None


def send_sms_warning(phone_number: str, district: str, risk_score: int, river_status: str) -> bool:
    client = get_twilio_client()
    if client is None or not TWILIO_FROM_NUMBER:
        logger.warning("Twilio not configured; SMS skipped for %s", phone_number)
        return False
    try:
        body = f"FloodSense alert: {district} risk score {risk_score}/10, river status {river_status}. Stay prepared and follow local authority advisories."
        client.messages.create(to=phone_number, from_=TWILIO_FROM_NUMBER, body=body)
        logger.info("SMS alert sent to %s for district %s", phone_number, district)
        return True
    except Exception:
        logger.exception("SMS alert failed for %s", phone_number)
        return False


def send_email_alert(email: str, district: str, risk_score: int, report_html: str) -> bool:
    client = get_sendgrid_client()
    if client is None or not SENDGRID_FROM_EMAIL:
        logger.warning("SendGrid not configured; email skipped for %s", email)
        return False
    try:
        html = f"""
        <html>
          <body>
            <h2>FloodSense Urgent District Alert</h2>
            <p><strong>District:</strong> {district}</p>
            <p><strong>Risk Score:</strong> {risk_score}/10</p>
            <hr />
            {report_html}
          </body>
        </html>
        """
        msg = Mail(
            from_email=Email(SENDGRID_FROM_EMAIL),
            to_emails=To(email),
            subject=f"Urgent Flood Alert: {district}",
            html_content=Content("text/html", html),
        )
        client.send(msg)
        logger.info("Email alert sent to %s for district %s", email, district)
        return True
    except Exception:
        logger.exception("Email alert failed for %s", email)
        return False


def _parse_bbox_overrides() -> Dict[str, Any]:
    try:
        raw = json.loads(DISTRICT_BBOX_OVERRIDES)
        if isinstance(raw, dict):
            return raw
    except Exception:
        logger.exception("Failed to parse DISTRICT_BBOX_OVERRIDES")
    return {}


def _init_gee() -> bool:
    try:
        if PROJECT_ID:
            ee.Initialize(project=PROJECT_ID)
        else:
            ee.Initialize()
        return True
    except Exception:
        logger.exception("GEE initialization failed")
        return False


def _fetch_fresh_sentinel_tile(district: str) -> Optional[Tuple[bytes, list[float]]]:
    bbox_map = _parse_bbox_overrides()
    bbox = bbox_map.get(district)
    if not bbox or not isinstance(bbox, list) or len(bbox) != 4:
        logger.info("No bbox override for district %s; skipping model inference", district)
        return None

    region = ee.Geometry.Rectangle(bbox)
    date_end = datetime.now(timezone.utc)
    date_start = date_end - timedelta(hours=3)

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(date_start.strftime("%Y-%m-%dT%H:%M:%S"), date_end.strftime("%Y-%m-%dT%H:%M:%S"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )

    if collection.size().getInfo() == 0:
        logger.info("No fresh Sentinel-1 tiles for %s in last 3 hours", district)
        return None

    image = collection.median()
    elevation = ee.Image("USGS/SRTMGL1_003")
    slope_mask = ee.Terrain.slope(elevation).lt(15)
    masked_image = image.updateMask(slope_mask).unmask(0)
    url = masked_image.getDownloadURL({"region": bbox, "dimensions": 512, "format": "GEO_TIFF", "bands": ["VV"]})
    res = requests.get(url, timeout=180)
    res.raise_for_status()
    return res.content, bbox


def _river_status_for_district(district: str, river_flows: list[dict[str, Any]]) -> str:
    d = district.lower()
    for row in river_flows:
        s = str(row.get("station", "")).lower()
        if d in s or s in d:
            return str(row.get("status", "NOT_RECEIVED"))
    return "NOT_RECEIVED"


def _extract_report_chunks(raw_text: str) -> dict[str, str]:
    chunks = {
        "situation_summary": "",
        "hydraulic_analysis": "",
        "historical_benchmark": "",
        "operational_actions": "",
        "confidence_score": "",
    }
    lines = [ln.strip() for ln in (raw_text or "").splitlines() if ln.strip()]
    section = None
    mapping = {
        "[SITUATION SUMMARY]": "situation_summary",
        "[HYDRAULIC ANALYSIS]": "hydraulic_analysis",
        "[HISTORICAL BENCHMARK]": "historical_benchmark",
        "[OPERATIONAL ACTIONS]": "operational_actions",
        "[CONFIDENCE]": "confidence_score",
    }
    for ln in lines:
        upper = ln.upper()
        found = None
        for key in mapping:
            if key in upper:
                found = key
                break
        if found:
            section = mapping[found]
            value = ln.split("]", 1)[-1].strip()
            if value:
                chunks[section] = value
            continue
        if section:
            chunks[section] = (chunks[section] + " " + ln).strip()
    return chunks


def _can_send_alert(profile_id: str, district: str) -> bool:
    key = (profile_id, district)
    now = datetime.now(timezone.utc)
    last = ALERT_STATE.get(key)
    if last is None:
        return True
    return now - last >= timedelta(hours=ALERT_COOLDOWN_HOURS)


def _mark_alert_sent(profile_id: str, district: str) -> None:
    ALERT_STATE[(profile_id, district)] = datetime.now(timezone.utc)


def _get_model():
    global _model
    if _model is None:
        _model = load_flood_model()
    return _model


def run_three_hour_cycle() -> None:
    logger.info("3-hour flood cycle started")
    try:
        supabase = get_supabase_client()
        if not _init_gee():
            logger.warning("GEE unavailable; cycle will continue with reduced coverage")

        river_flows = get_ffc_data()
        ai = FloodAI()
        district_rows = (
            supabase.table("profiles")
            .select("district")
            .not_.is_("district", "null")
            .execute()
        )
        districts = sorted({row["district"] for row in (district_rows.data or []) if row.get("district")})

        if not districts:
            logger.info("No subscribed districts found in profiles")
            return

        for district in districts:
            try:
                tile = _fetch_fresh_sentinel_tile(district)
                if tile is None:
                    continue
                image_bytes, bbox = tile
                model_out = predict_flood(_get_model(), image_bytes, district, bbox)
                river_status = _river_status_for_district(district, river_flows)
                current_pct = float(model_out["water_coverage_pct"])
                delta_vs_2010 = 0.0

                risk = ai.calculate_defensible_risk(
                    {
                        "flood_pct_current": current_pct,
                        "flood_pct_2010": current_pct - delta_vs_2010,
                        "river_status": river_status,
                    },
                    river_flows,
                )
                risk_score = int(max(1, min(10, round(risk))))

                supabase.table("district_risk_status").upsert(
                    {
                        "district": district,
                        "current_flood_pct": current_pct,
                        "delta_vs_2010": delta_vs_2010,
                        "risk_score": risk_score,
                        "river_status": river_status if river_status in {"NORMAL", "HIGH", "EXTREME", "NOT_RECEIVED"} else "NOT_RECEIVED",
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                    }
                ).execute()

                report_text = ai.generate_insights(
                    [
                        {
                            "district": district,
                            "flood_pct_current": current_pct,
                            "flood_pct_2010": current_pct - delta_vs_2010,
                            "river_status": river_status,
                        }
                    ],
                    river_flows,
                )
                chunks = _extract_report_chunks(report_text)
                supabase.table("tactical_reports").insert(
                    {"district": district, **chunks}
                ).execute()

                if risk_score < 7:
                    continue

                profiles = (
                    supabase.table("profiles")
                    .select("id,email,phone_number,notification_preference")
                    .eq("district", district)
                    .execute()
                )

                for profile in (profiles.data or []):
                    profile_id = str(profile.get("id", ""))
                    if not profile_id or not _can_send_alert(profile_id, district):
                        continue

                    pref = str(profile.get("notification_preference") or "email")
                    sent_any = False

                    if pref in {"sms", "both"} and profile.get("phone_number"):
                        sent_any = send_sms_warning(profile["phone_number"], district, risk_score, river_status) or sent_any
                    if pref in {"email", "both"} and profile.get("email"):
                        sent_any = send_email_alert(profile["email"], district, risk_score, report_text.replace("\n", "<br/>")) or sent_any

                    if sent_any:
                        _mark_alert_sent(profile_id, district)
            except Exception:
                logger.exception("District cycle failed for %s", district)
    except Exception:
        logger.exception("3-hour flood cycle failed")
    finally:
        logger.info("3-hour flood cycle finished")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(run_three_hour_cycle, "interval", hours=3, id="flood_cycle_3h", replace_existing=True)
    _scheduler.start()
    logger.info("Background scheduler started (3-hour cycle)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background scheduler stopped")
