import time
from fastapi import APIRouter
from backend.monitoring.health import full_health_check

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness():
    """K8s liveness probe — is the process alive?"""
    return {"status": "alive", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


@router.get("/health/ready")
async def readiness():
    """K8s readiness probe — is the app ready to serve traffic?"""
    return {"status": "ready", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


@router.get("/health/deep")
async def deep_health():
    """Full system health — DB, Redis, Ollama, Celery queue depth."""
    result = await full_health_check()
    return result
