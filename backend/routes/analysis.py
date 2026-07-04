"""District flood analysis — background jobs, results, map imagery, insights."""

from fastapi import APIRouter, Path, Query, Response

from .. import jobs
from ..schemas import AnalysisJobResponse
from ..services import analysis, rivers
from ..services.ai import generate_insights

router = APIRouter(tags=["Analysis"])


@router.post(
    "/analysis/{district}", response_model=AnalysisJobResponse, status_code=202
)
def start_analysis(district: str = Path(..., min_length=2)):
    """Queue a full analysis (SAR + U-Net + rivers + 2010 benchmark) for a district.

    Returns a job_id immediately — poll GET /api/jobs/{job_id} until the status
    is `complete`, then read GET /api/analysis/{district}/latest.
    """
    # Validate the district up-front so bad names fail fast, not inside the job.
    from ..services import geodata

    actual_name, _, _ = geodata.find_district(district)

    job = jobs.submit_analysis_job(actual_name, analysis.run_district_analysis)
    return AnalysisJobResponse(
        job_id=job["job_id"],
        status=job["status"],
        district=actual_name,
        message=f"Analysis queued. Poll GET /api/jobs/{job['job_id']} for progress.",
    )


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Status of a background analysis job (queued | running | complete | failed)."""
    return {"success": True, "job": jobs.get_job(job_id)}


@router.get("/analysis")
def list_latest_analyses(limit: int = Query(200, ge=1, le=500)):
    """Newest analysis per district, sorted by risk (national overview screens)."""
    docs = analysis.latest_analyses_all(limit=limit)
    return {"success": True, "count": len(docs), "analyses": docs}


@router.get("/analysis/{district}/latest")
def get_latest_analysis(
    district: str,
    include_image: bool = Query(
        False, description="Include the base64 flood-map PNG (large payload)."
    ),
):
    """The most recent stored analysis for a district."""
    return {
        "success": True,
        "analysis": analysis.latest_analysis(district, include_image=include_image),
    }


@router.get("/analysis/{district}/image")
def get_analysis_image(district: str):
    """The latest flood-map overlay as a raw PNG (usable directly in <img> tags)."""
    png = analysis.latest_analysis_image_png(district)
    return Response(content=png, media_type="image/png")


@router.get("/analysis/{district}/insights")
def get_insights(district: str):
    """AI strategic insights (Gemini/Groq) grounded in the latest analysis."""
    doc = analysis.latest_analysis(district)
    try:
        stations = rivers.get_river_data()["stations"]
    except Exception:
        stations = []
    return {"success": True, **generate_insights(doc, stations)}
