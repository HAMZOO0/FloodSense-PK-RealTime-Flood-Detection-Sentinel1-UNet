from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Any, Dict
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import Client, create_client
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from app.engine.cron_worker import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("floodsense.api")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")

app = FastAPI(
    title="FloodSense API",
    version="1.0.0",
    description="Production-ready API surface for flood analysis workflows.",
)

TASKS: Dict[str, Dict[str, Any]] = {}
TASKS_LOCK = Lock()


def _get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise HTTPException(status_code=500, detail="Supabase service credentials are not configured")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _get_twilio_verify_client() -> TwilioClient:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_VERIFY_SERVICE_SID:
        raise HTTPException(status_code=500, detail="Twilio Verify is not configured")
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


class VerifyOtpPayload(BaseModel):
    phone_number: str
    otp_code: str


@app.on_event("startup")
def on_startup() -> None:
    try:
        start_scheduler()
    except Exception:
        logger.exception("Failed to start scheduler")


@app.on_event("shutdown")
def on_shutdown() -> None:
    try:
        stop_scheduler()
    except Exception:
        logger.exception("Failed to stop scheduler")


def _set_task_state(task_id: str, **fields: Any) -> None:
    with TASKS_LOCK:
        if task_id in TASKS:
            TASKS[task_id].update(fields)


def run_flood_pipeline(task_id: str, district: str) -> None:
    _set_task_state(task_id, status="PROCESSING")

    try:
        mock_metrics = {
            "district": district,
            "water_coverage_pct": 14.62,
            "affected_area_km2": 382.4,
            "risk_score": 7,
            "report": (
                f"Flood pipeline completed for {district}. "
                "Elevated inundation risk detected in low-lying zones."
            ),
        }
        _set_task_state(task_id, status="SUCCESS", result=mock_metrics)
    except Exception as exc:
        _set_task_state(
            task_id,
            status="FAILED",
            result={"error": str(exc), "district": district},
        )


@app.post("/api/v1/analysis/trigger")
def trigger_analysis(district: str, background_tasks: BackgroundTasks) -> Dict[str, str]:
    task_id = str(uuid4())
    with TASKS_LOCK:
        TASKS[task_id] = {"task_id": task_id, "status": "PENDING", "result": None}

    background_tasks.add_task(run_flood_pipeline, task_id, district)
    return {"task_id": task_id, "status": "PENDING"}


@app.get("/api/v1/analysis/status/{task_id}")
def get_analysis_status(task_id: str) -> Dict[str, Any]:
    with TASKS_LOCK:
        task = TASKS.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/v1/maps/render/{task_id}", response_class=HTMLResponse)
def render_map(task_id: str) -> HTMLResponse:
    with TASKS_LOCK:
        task = TASKS.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Flood Map Render</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #0b1220;
      color: #f4f7ff;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      width: min(92vw, 780px);
      border: 1px solid #22304a;
      background: #111a2c;
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
    }}
    h1 {{
      margin-top: 0;
      font-size: 1.2rem;
    }}
    .meta {{
      color: #9db0d3;
      font-size: 0.95rem;
      margin-bottom: 16px;
    }}
    .placeholder {{
      border: 1px dashed #3f5277;
      border-radius: 10px;
      padding: 26px;
      text-align: center;
      background: #0f1726;
    }}
  </style>
</head>
<body>
  <section class="card">
    <h1>Flood Map WebView Placeholder</h1>
    <p class="meta">Task ID: {task_id} | Status: {task["status"]}</p>
    <div class="placeholder">
      This container will render Pydeck/Folium map output for the mobile WebView.
    </div>
  </section>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@app.get("/api/status/{district}")
def get_district_status(district: str) -> Dict[str, Any]:
    try:
        supabase = _get_supabase()
        risk_resp = (
            supabase.table("district_risk_status")
            .select("*")
            .eq("district", district)
            .limit(1)
            .execute()
        )
        if not risk_resp.data:
            raise HTTPException(status_code=404, detail="District status not found")

        report_resp = (
            supabase.table("tactical_reports")
            .select("situation_summary,hydraulic_analysis,historical_benchmark,operational_actions,confidence_score,created_at")
            .eq("district", district)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return {"district_risk_status": risk_resp.data[0], "latest_tactical_report": report_resp.data[0] if report_resp.data else None}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch district status for %s", district)
        raise HTTPException(status_code=500, detail="Failed to fetch district status")


@app.post("/api/verify-otp")
def verify_otp(payload: VerifyOtpPayload) -> Dict[str, Any]:
    try:
        client = _get_twilio_verify_client()
        check = (
            client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID)
            .verification_checks.create(to=payload.phone_number, code=payload.otp_code)
        )
        approved = check.status == "approved"
        return {"phone_number": payload.phone_number, "verified": approved, "status": check.status}
    except TwilioRestException as exc:
        logger.warning("OTP verification failed for %s: %s", payload.phone_number, exc.msg)
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    except HTTPException:
        raise
    except Exception:
        logger.exception("OTP verification internal failure for %s", payload.phone_number)
        raise HTTPException(status_code=500, detail="OTP verification failed")
