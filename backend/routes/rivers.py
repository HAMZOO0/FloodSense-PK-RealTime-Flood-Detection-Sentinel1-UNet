"""Live FFD river-flow data (Indus barrages/gauges) with Mongo caching."""

from fastapi import APIRouter, Query

from ..services import rivers

router = APIRouter(prefix="/rivers", tags=["Rivers"])


@router.get("")
def get_rivers(
    max_age_minutes: int = Query(
        None, ge=0, le=1440, description="Serve cache younger than this; default 30."
    ),
    force_refresh: bool = Query(False, description="Bypass the cache and scrape live."),
):
    """All FFD stations: inflow/outflow (cusecs), trend, and NORMAL/HIGH/EXTREME status."""
    data = rivers.get_river_data(max_age_minutes=max_age_minutes, force_refresh=force_refresh)
    return {"success": True, "count": len(data["stations"]), **data}


@router.get("/{station_name}")
def get_station(station_name: str):
    """A single station matched by (partial, case-insensitive) name."""
    return {"success": True, **rivers.get_station(station_name)}
