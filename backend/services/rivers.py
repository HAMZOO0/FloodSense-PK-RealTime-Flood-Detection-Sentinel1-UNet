"""Live FFD river-flow data with a MongoDB snapshot cache.

The scraper (scrapers/ffc_scraper.py) already falls back to its local JSON
cache; here we additionally persist snapshots to Mongo so web and mobile get
consistent data and we don't hammer ffd.pmd.gov.pk on every request.
"""

import logging
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db import require_db
from ..errors import not_found, service_unavailable

logger = logging.getLogger("floodsense.rivers")


def _latest_snapshot(db, max_age_minutes: int):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    return db.rivers.find_one(
        {"fetched_at": {"$gte": cutoff}}, sort=[("fetched_at", -1)]
    )


def get_river_data(max_age_minutes: int | None = None, force_refresh: bool = False) -> dict:
    """Return {stations, fetched_at, source} — live scrape or Mongo cache."""
    max_age = (
        settings.RIVER_CACHE_MINUTES if max_age_minutes is None else max_age_minutes
    )
    db = require_db()

    if not force_refresh:
        snapshot = _latest_snapshot(db, max_age)
        if snapshot and snapshot.get("stations"):
            return {
                "stations": snapshot["stations"],
                "fetched_at": snapshot["fetched_at"].isoformat(),
                "source": "cache",
            }

    from scrapers.ffc_scraper import get_ffc_data

    try:
        stations = get_ffc_data()
    except Exception as e:
        logger.error("FFD scrape crashed: %s", e)
        stations = []

    if stations:
        fetched_at = datetime.now(timezone.utc)
        db.rivers.insert_one({"fetched_at": fetched_at, "stations": stations})
        return {
            "stations": stations,
            "fetched_at": fetched_at.isoformat(),
            "source": "live",
        }

    # Live fetch failed — fall back to the newest snapshot of any age.
    stale = db.rivers.find_one(sort=[("fetched_at", -1)])
    if stale and stale.get("stations"):
        return {
            "stations": stale["stations"],
            "fetched_at": stale["fetched_at"].isoformat(),
            "source": "stale-cache",
        }

    raise service_unavailable(
        "RIVER_DATA_UNAVAILABLE",
        "Could not fetch FFD river data and no cached snapshot exists yet.",
    )


def get_station(station_name: str) -> dict:
    data = get_river_data()
    target = station_name.lower().strip()
    for row in data["stations"]:
        if target in (row.get("station") or "").lower():
            return {"station": row, "fetched_at": data["fetched_at"], "source": data["source"]}
    raise not_found(
        "STATION_NOT_FOUND",
        f"No FFD station matching '{station_name}'. See GET /api/rivers for the list.",
    )


def match_station_to_district(district_name: str, stations: list[dict]) -> dict | None:
    """Same inclusion-matching used by the dashboard and mobile app."""
    dn = district_name.lower().strip()
    for row in stations:
        st_name = (row.get("station") or "").lower()
        if dn in st_name or st_name in dn:
            return row
    return None
