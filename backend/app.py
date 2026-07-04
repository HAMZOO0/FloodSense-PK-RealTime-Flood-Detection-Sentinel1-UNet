"""FloodSense-PK REST API entry point.

Run from the project root:
    uvicorn backend.app:app --host 0.0.0.0 --port 8000

Interactive docs: http://localhost:8000/docs
"""

import logging
import os
import sys

# Make the project root importable (scrapers/, utils/, models/, agent/, rag/)
# regardless of where uvicorn is launched from.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _setup_console():
    """Windows cp1252 consoles crash on emoji unless UTF-8 is enabled."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_setup_console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("floodsense.app")

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, jobs
from .config import settings
from .errors import register_exception_handlers
from .routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — best-effort: the API boots even if Mongo is briefly down
    # (data routes return 503 until it recovers).
    if not settings.MONGO_URI:
        logger.warning("MONGO_URI is not set — all data routes will return 503.")
    else:
        db.ensure_indexes()
    logger.info("FloodSense-PK API ready.")
    yield
    # Shutdown
    jobs.shutdown()
    db.close()


app = FastAPI(
    title="FloodSense-PK API",
    description=(
        "National Flood Intelligence & Early Warning System for Pakistan — "
        "REST backend serving the web dashboard and mobile app. "
        "Satellite SAR + U-Net detection, live FFD river flows, the 2010 "
        "historical benchmark, the four-agent disaster workflow, and the RAG "
        "knowledge assistant."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Web + mobile clients live on other origins (Streamlit, Flet, browsers).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/", tags=["Health"])
def root():
    """API landing — points clients at the docs and health check."""
    return {
        "success": True,
        "service": "FloodSense-PK API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
