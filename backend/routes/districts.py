"""District catalogue — names, metadata, and GeoJSON geometry for maps."""

from fastapi import APIRouter, Query

from ..services import geodata

router = APIRouter(prefix="/districts", tags=["Districts"])


@router.get("")
def list_districts(priority_only: bool = Query(False, description="Only flood-priority districts.")):
    """All district names (for dropdowns / pickers on web and mobile)."""
    from utils.districts import PRIORITY_DISTRICTS

    names = geodata.list_district_names()
    priority_set = {p.lower() for p in PRIORITY_DISTRICTS}
    districts = [
        {
            "name": n,
            "is_priority": any(p in n.lower() for p in priority_set),
        }
        for n in names
    ]
    if priority_only:
        districts = [d for d in districts if d["is_priority"]]
    return {"success": True, "count": len(districts), "districts": districts}


@router.get("/{name}")
def get_district(name: str):
    """Metadata for one district: bbox, centroid, area, priority flag."""
    return {"success": True, "district": geodata.district_info(name)}


@router.get("/{name}/geometry")
def get_district_geometry(name: str):
    """District boundary as a GeoJSON Feature (for map rendering)."""
    return {"success": True, "feature": geodata.district_geometry_geojson(name)}
