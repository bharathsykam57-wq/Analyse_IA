import os
import time
import logging
import httpx
import redis

logger = logging.getLogger(__name__)


async def check_ollama():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            mistral_ok = any("mistral-nemo" in m for m in models)
            return {
                "status": "ok" if mistral_ok else "degraded",
                "models": models,
                "mistral_nemo": mistral_ok,
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_redis():
    try:
        r = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_timeout=3,
        )
        r.ping()
        queue_depth = r.llen("celery")
        return {"status": "ok", "queue_depth": queue_depth}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def full_health_check():
    start = time.time()
    ollama = await check_ollama()
    redis_status = check_redis()
    all_ok = (
        ollama["status"] == "ok"
        and redis_status["status"] == "ok"
    )
    return {
        "status": "ok" if all_ok else "degraded",
        "latency_ms": round((time.time() - start) * 1000, 2),
        "checks": {
            "ollama": ollama,
            "redis": redis_status,
        },
    }
