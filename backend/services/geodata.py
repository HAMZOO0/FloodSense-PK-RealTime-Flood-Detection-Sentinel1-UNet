"""District geometry lookups backed by pakistan_districts.json (loaded once)."""

import os
import threading
from functools import lru_cache

from ..config import settings
from ..errors import not_found, service_unavailable

_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load_gdf():
    """Load the district GeoDataFrame once and detect its name column."""
    import geopandas as gpd

    from utils.districts import detect_name_column

    if not os.path.exists(settings.SHAPEFILE):
        raise service_unavailable(
            "SHAPEFILE_MISSING",
            f"District shapefile not found at {settings.SHAPEFILE}.",
        )
    gdf = gpd.read_file(settings.SHAPEFILE)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    name_col = detect_name_column(gdf)
    if not name_col:
        raise service_unavailable(
            "SHAPEFILE_INVALID", "Could not detect a district-name column."
        )
    return gdf, name_col


def load_districts():
    with _lock:
        return _load_gdf()


def list_district_names() -> list[str]:
    gdf, name_col = load_districts()
    return sorted({str(n) for n in gdf[name_col].dropna()})


def find_district(name: str):
    """Resolve a district by exact (then partial) case-insensitive match.

    Returns (actual_name, shapely_geometry, bbox[minx, miny, maxx, maxy]).
    """
    gdf, name_col = load_districts()
    target = name.lower().strip()

    mask = gdf[name_col].apply(lambda x: str(x).lower() == target)
    if not mask.any():
        mask = gdf[name_col].apply(lambda x: target in str(x).lower())
    if not mask.any():
        raise not_found(
            "DISTRICT_NOT_FOUND",
            f"District '{name}' was not found. Use GET /api/districts for valid names.",
        )

    row = gdf[mask].iloc[0]
    return str(row[name_col]), row.geometry, list(row.geometry.bounds)


def district_area_km2(geom) -> float | None:
    """Equal-area size in km² (EPSG:6933); None if it cannot be computed."""
    try:
        import geopandas as gpd

        area_m2 = (
            gpd.GeoSeries([geom], crs="EPSG:4326").to_crs("EPSG:6933").area.iloc[0]
        )
        return float(area_m2) / 1_000_000 if area_m2 > 0 else None
    except Exception:
        return None


def district_info(name: str) -> dict:
    from utils.districts import PRIORITY_DISTRICTS

    actual_name, geom, bbox = find_district(name)
    centroid = geom.centroid
    return {
        "name": actual_name,
        "bbox": bbox,
        "centroid": {"lat": float(centroid.y), "lon": float(centroid.x)},
        "area_km2": district_area_km2(geom),
        "is_priority": any(
            p.lower() in actual_name.lower() for p in PRIORITY_DISTRICTS
        ),
    }


def district_geometry_geojson(name: str) -> dict:
    from shapely.geometry import mapping

    actual_name, geom, bbox = find_district(name)
    return {
        "type": "Feature",
        "properties": {"district": actual_name, "bbox": bbox},
        "geometry": mapping(geom),
    }
