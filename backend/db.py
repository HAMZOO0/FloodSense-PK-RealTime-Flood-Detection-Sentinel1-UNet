"""MongoDB access layer (sync PyMongo — FastAPI runs sync routes in a threadpool).

Collections:
    users     — mobile/web accounts {username, password_hash, district, created_at}
    analyses  — completed district analyses (SAR + U-Net + rivers + risk)
    alerts    — auto/pipeline/manual flood alerts per district
    jobs      — background analysis job records
    rivers    — cached FFD river snapshots
    chats     — RAG chat history
"""

import logging
from typing import Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from .config import settings
from .errors import APIError, service_unavailable

logger = logging.getLogger("floodsense.db")

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if not settings.MONGO_URI:
            raise service_unavailable(
                "MONGO_NOT_CONFIGURED",
                "MONGO_URI is not set in the environment / .env file.",
            )
        _client = MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
        )
    return _client


def get_db() -> Database:
    return get_client()[settings.MONGO_DB_NAME]


def require_db() -> Database:
    """Return the database, translating connectivity failures into a 503."""
    try:
        db = get_db()
        db.client.admin.command("ping")
        return db
    except APIError:
        raise
    except PyMongoError as e:
        raise service_unavailable(
            "MONGO_UNAVAILABLE", f"Could not reach MongoDB: {e}"
        )


def ping() -> bool:
    """Best-effort connectivity check used by /api/health."""
    try:
        get_db().client.admin.command("ping")
        return True
    except Exception as e:
        logger.warning("Mongo ping failed: %s", e)
        return False


def ensure_indexes() -> None:
    """Create the indexes the API relies on (idempotent)."""
    try:
        db = get_db()
        db.users.create_index([("username", ASCENDING)], unique=True)
        db.analyses.create_index([("district", ASCENDING), ("created_at", DESCENDING)])
        db.alerts.create_index([("district", ASCENDING), ("created_at", DESCENDING)])
        db.jobs.create_index([("job_id", ASCENDING)], unique=True)
        db.rivers.create_index([("fetched_at", DESCENDING)])
        db.chats.create_index([("created_at", DESCENDING)])
        logger.info("Mongo indexes ensured on '%s'.", settings.MONGO_DB_NAME)
    except Exception as e:
        # Startup should not crash if Mongo is briefly down — routes will 503.
        logger.warning("Could not ensure Mongo indexes: %s", e)


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def serialize(doc: Optional[dict], *, exclude: tuple = ()) -> Optional[dict]:
    """Convert a Mongo document into a JSON-safe dict (`_id` → `id` string)."""
    if doc is None:
        return None
    out = {k: v for k, v in doc.items() if k not in exclude}
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    return out
