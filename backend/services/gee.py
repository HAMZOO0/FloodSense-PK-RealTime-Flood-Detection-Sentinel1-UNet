"""Google Earth Engine initialisation (once per process, thread-safe).

Supports two auth modes:
1. Service account — GEE_CLIENT_EMAIL + GEE_PRIVATE_KEY env vars (cloud deploys).
2. Local credentials — `earthengine authenticate` + optional PROJECT_ID.
"""

import logging
import threading

from ..config import settings
from ..errors import service_unavailable

logger = logging.getLogger("floodsense.gee")

_lock = threading.Lock()
_initialized = False
_init_error: str = ""


def init_gee() -> None:
    """Initialise GEE once; raise a 503 APIError if it cannot be reached."""
    global _initialized, _init_error
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        import ee

        try:
            if settings.GEE_CLIENT_EMAIL and settings.GEE_PRIVATE_KEY:
                key = settings.GEE_PRIVATE_KEY.replace("\\n", "\n")
                credentials = ee.ServiceAccountCredentials(
                    settings.GEE_CLIENT_EMAIL, key_data=key
                )
                ee.Initialize(credentials, project=settings.PROJECT_ID or None)
            elif settings.PROJECT_ID:
                ee.Initialize(project=settings.PROJECT_ID)
            else:
                ee.Initialize()
            _initialized = True
            _init_error = ""
            logger.info("Google Earth Engine initialised.")
        except Exception as e:
            _init_error = str(e)
            logger.error("GEE initialisation failed: %s", e)
            raise service_unavailable(
                "GEE_UNAVAILABLE",
                f"Google Earth Engine could not be initialised: {e}. "
                "Run 'earthengine authenticate' or set GEE_* service-account vars.",
            )


def gee_status() -> dict:
    """Non-throwing status snapshot for /api/health."""
    return {"initialized": _initialized, "error": _init_error or None}
