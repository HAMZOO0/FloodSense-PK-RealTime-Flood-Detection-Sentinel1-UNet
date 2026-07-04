"""Agentic disaster workflow endpoint logic.

Feeds the latest stored analysis for a district into the four-agent
orchestrator (Data Fusion → Intelligence → Simulation → Response) and persists
the generated citizen/authority alerts.
"""

import logging
from datetime import datetime, timezone

from ..config import settings
from ..db import require_db
from . import geodata
from .analysis import latest_analysis
from .rag import build_rag_context_for_district

logger = logging.getLogger("floodsense.pipeline")


def _map_river_trend(trend: str):
    from agent.schemas import RiverTrend

    t = (trend or "").lower()
    if "ris" in t:
        return RiverTrend.RISING
    if "fall" in t:
        return RiverTrend.FALLING
    return RiverTrend.STABLE


def _map_river_status(status: str):
    from agent.schemas import RiverStatus

    s = (status or "").upper()
    if "EXTREME" in s:
        return RiverStatus.EXTREME
    if "HIGH" in s:
        return RiverStatus.HIGH
    return RiverStatus.NORMAL


def run_district_pipeline(district: str, population_at_risk: int | None = None) -> dict:
    """Run the full four-agent workflow using the latest analysis for `district`."""
    from agent.pipeline import run_pipeline
    from agent.schemas import (
        HistoricalIntelligence,
        HydraulicIntelligence,
        RiverStatus,
        RiverTrend,
        SatelliteIntelligence,
    )

    analysis = latest_analysis(district)  # raises 404 if no analysis exists yet
    actual_name = analysis["district"]

    satellite = SatelliteIntelligence(
        district=actual_name,
        flood_extent_percentage=min(float(analysis["flood_pct_current"]), 100.0),
        affected_area_km2=float(analysis["affected_area_km2"]),
    )

    station = analysis.get("river")
    if station:
        hydraulic = HydraulicIntelligence(
            station=station.get("station", actual_name),
            river_discharge_cusecs=float(station.get("inflow", 0) or 0),
            inflow_cusecs=float(station.get("inflow", 0) or 0),
            outflow_cusecs=float(station.get("outflow", 0) or 0),
            trend=_map_river_trend(station.get("inflow_trend")),
            status=_map_river_status(station.get("status")),
        )
    else:
        hydraulic = HydraulicIntelligence(
            station=f"{actual_name} (no gauge)",
            river_discharge_cusecs=0.0,
            inflow_cusecs=0.0,
            outflow_cusecs=0.0,
            trend=RiverTrend.STABLE,
            status=RiverStatus.NORMAL,
        )

    historical = HistoricalIntelligence(
        benchmark_year=2010,
        benchmark_flood_percentage=min(float(analysis["flood_pct_2010"]), 100.0),
    )

    rag_context = build_rag_context_for_district(actual_name)

    if population_at_risk is None:
        population_at_risk = int(
            float(analysis["affected_area_km2"])
            * settings.ESTIMATED_POP_DENSITY_PER_KM2
        )

    # Simulation needs the district area only when current coverage is ~0%.
    district_area = None
    if float(analysis["flood_pct_current"]) <= 0.01:
        _, geom, _ = geodata.find_district(actual_name)
        district_area = geodata.district_area_km2(geom)

    result = run_pipeline(
        satellite,
        hydraulic,
        historical,
        rag_context,
        population_at_risk=population_at_risk,
        district_area_km2=district_area,
    )

    payload = result.model_dump(mode="json")
    payload["district"] = actual_name
    payload["population_at_risk"] = population_at_risk
    payload["rag_sources"] = list(rag_context.sources)
    payload["based_on_analysis_id"] = analysis.get("id")

    _persist_pipeline_alerts(actual_name, payload)
    return payload


def _persist_pipeline_alerts(district: str, payload: dict) -> None:
    """Store the Response Agent's citizen + authority alerts (best-effort)."""
    try:
        db = require_db()
        risk_level = payload.get("assessment", {}).get("risk_level", "")
        severity = (
            "HIGH"
            if "HIGH" in risk_level
            else "MODERATE" if "MODERATE" in risk_level else "LOW"
        )
        now = datetime.now(timezone.utc)
        db.alerts.insert_many(
            [
                {
                    "district": district,
                    "severity": severity,
                    "message": payload.get("citizen_alert", ""),
                    "audience": "citizen",
                    "source": "pipeline",
                    "created_at": now,
                },
                {
                    "district": district,
                    "severity": severity,
                    "message": payload.get("authority_alert", ""),
                    "audience": "authority",
                    "source": "pipeline",
                    "created_at": now,
                },
            ]
        )
    except Exception as e:
        logger.warning("Could not persist pipeline alerts: %s", e)
