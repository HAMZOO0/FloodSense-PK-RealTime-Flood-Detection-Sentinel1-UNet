"""Service health / readiness."""

from fastapi import APIRouter

from .. import db
from ..services.gee import gee_status
from ..services.model import model_status

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    """Liveness + dependency status for monitoring and client splash screens."""
    mongo_ok = db.ping()
    return {
        "success": True,
        "status": "ok" if mongo_ok else "degraded",
        "mongo": mongo_ok,
        "gee": gee_status(),
        "model": model_status(),
        "version": "1.0.0",
    }
