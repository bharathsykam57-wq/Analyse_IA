import os
import time
import logging
import httpx
import redis
from backend.utils.redis_config import get_redis_url
from backend.monitoring.langfuse_client import get_langfuse
from backend.monitoring.mlflow_client import check_mlflow_status

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_REQUIRED = os.getenv("OLLAMA_REQUIRED", "true").lower() == "true"


async def check_ollama():
    if not OLLAMA_REQUIRED:
        return {
            "status": "skipped",
            "reason": "OLLAMA_REQUIRED=false",
            "url": OLLAMA_URL,
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            mistral_ok = any("mistral-nemo" in m for m in models)
            return {
                "status": "ok" if mistral_ok else "degraded",
                "models": models,
                "mistral_nemo": mistral_ok,
                "url": OLLAMA_URL,
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": OLLAMA_URL}


def check_redis():
    try:
        r = redis.Redis.from_url(
            get_redis_url(),
            socket_timeout=3,
        )
        r.ping()
        queue_depth = r.llen("celery")
        return {"status": "ok", "queue_depth": queue_depth}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_langfuse():
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        return {
            "status": "skipped",
            "reason": "LANGFUSE keys not configured",
            "host": host,
        }

    try:
        client = get_langfuse()
        if client is None:
            return {
                "status": "error",
                "reason": "Langfuse client initialization failed",
                "host": host,
            }
        return {"status": "ok", "host": host}
    except Exception as e:
        return {"status": "error", "error": str(e), "host": host}


async def full_health_check():
    start = time.time()
    ollama = await check_ollama()
    redis_status = check_redis()
    langfuse_status = check_langfuse()
    mlflow_status = check_mlflow_status()
    all_ok = (
        ollama["status"] in {"ok", "skipped"}
        and redis_status["status"] == "ok"
        and langfuse_status["status"] in {"ok", "skipped"}
        and mlflow_status["status"] in {"ok", "skipped"}
    )
    return {
        "status": "ok" if all_ok else "degraded",
        "latency_ms": round((time.time() - start) * 1000, 2),
        "checks": {
            "ollama": ollama,
            "redis": redis_status,
            "langfuse": langfuse_status,
            "mlflow": mlflow_status,
        },
    }
