import time
import os
import json
import redis
from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from backend.monitoring.health import full_health_check
from backend.monitoring.metrics import render_prometheus_text
from backend.monitoring.analytics_tracker import (
    get_analytics_summary_sync,
    get_analytics_dashboard_cards_sync,
    get_upload_distribution_sync,
)
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


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    return PlainTextResponse(
        content=render_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


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


@router.get("/ops/analytics/summary")
async def get_analytics_summary(
    days: int = Query(default=7, ge=1, le=90),
    x_ops_token: str | None = Header(default=None),
):
    """Get aggregated analytics summary for dashboard metrics (ops-only)."""
    _verify_ops_token(x_ops_token)
    return get_analytics_summary_sync(days=days)


@router.get("/ops/analytics/dashboard")
async def get_analytics_dashboard_cards(
    days: int = Query(default=7, ge=1, le=90),
    x_ops_token: str | None = Header(default=None),
):
    """Get dashboard-ready analytics cards (ops-only)."""
    _verify_ops_token(x_ops_token)
    return get_analytics_dashboard_cards_sync(days=days)


@router.get("/ops/analytics/uploads")
async def get_analytics_upload_distribution(
    days: int = Query(default=7, ge=1, le=90),
    x_ops_token: str | None = Header(default=None),
):
    """Get upload size/type distribution analytics (ops-only)."""
    _verify_ops_token(x_ops_token)
    return get_upload_distribution_sync(days=days)
