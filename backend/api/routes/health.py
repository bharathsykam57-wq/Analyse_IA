import time
import os
import json
import redis
from fastapi import APIRouter, Header, HTTPException, Query, status
from backend.monitoring.health import full_health_check
from backend.utils.redis_config import get_redis_url

router = APIRouter(tags=["health"])

REDIS_URL = get_redis_url()
CELERY_DLQ_KEY = os.getenv("CELERY_DLQ_KEY", "celery:dead_letter_tasks")
OPS_API_TOKEN = os.getenv("OPS_API_TOKEN")


def _verify_ops_token(x_ops_token: str | None):
    if not OPS_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPS_API_TOKEN is not configured",
        )

    if x_ops_token != OPS_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ops token",
        )


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


@router.get("/ops/celery/dlq")
async def get_celery_dead_letter(
    limit: int = Query(default=50, ge=1, le=500),
    x_ops_token: str | None = Header(default=None),
):
    """Inspect recent dead-lettered Celery failures (ops-only).

    Authentication:
    - Requires `OPS_API_TOKEN` env var on backend
    - Client must send matching `X-Ops-Token` header
    """
    _verify_ops_token(x_ops_token)

    try:
        r = redis.from_url(REDIS_URL)
        raw_items = r.lrange(CELERY_DLQ_KEY, 0, limit - 1)
        items = []
        for raw in raw_items:
            try:
                decoded = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
                items.append(json.loads(decoded))
            except Exception:
                items.append({"raw": str(raw)})

        return {
            "status": "ok",
            "key": CELERY_DLQ_KEY,
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dead-letter queue: {e}",
        )
