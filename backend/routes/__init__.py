"""API route registry — every router mounts under the /api prefix."""

from fastapi import APIRouter

from . import alerts, analysis, auth, chat, districts, health, pipeline, rivers

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(districts.router)
api_router.include_router(rivers.router)
api_router.include_router(analysis.router)
api_router.include_router(pipeline.router)
api_router.include_router(alerts.router)
api_router.include_router(chat.router)
