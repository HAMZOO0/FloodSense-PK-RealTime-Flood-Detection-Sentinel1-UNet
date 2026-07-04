"""Agentic Command Center — the four-agent disaster workflow over HTTP."""

from fastapi import APIRouter, Body

from ..schemas import PipelineRequest
from ..services.pipeline import run_district_pipeline

router = APIRouter(prefix="/pipeline", tags=["Agent Pipeline"])


@router.post("/{district}")
def run_pipeline_for_district(
    district: str, body: PipelineRequest = Body(default=PipelineRequest())
):
    """Run Data Fusion → Intelligence → Simulation → Response for a district.

    Requires a completed analysis for the district (POST /api/analysis/{district}
    first). Returns the risk assessment, flood progression, and the citizen +
    authority alerts (which are also persisted to the alerts collection).
    """
    result = run_district_pipeline(
        district, population_at_risk=body.population_at_risk
    )
    return {"success": True, "pipeline": result}
