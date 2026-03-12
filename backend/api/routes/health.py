# backend/api/routes/health.py
"""Health check endpoints following Kubernetes liveness/readiness pattern.

Provides three health check endpoints:
- GET /health/live: Liveness probe (is app running?)
- GET /health/ready: Readiness probe (is app ready for requests?)
- GET /health: Full status (detailed service health)

Status Codes:
- 200 OK: Service(s) healthy and operational
- 503 Service Unavailable: Critical service(s) degraded/unhealthy
"""

from fastapi import APIRouter, Response
import redis
import os
import logging
import httpx
import json
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Connection pools (static for reuse across requests)
_redis_conn: Optional[redis.Redis] = None
_db_engine = None


def get_redis_conn():
    """Get or create Redis connection pool."""
    global _redis_conn
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    if _redis_conn is None:
        try:
            _redis_conn = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            _redis_conn.ping()
            logger.debug("Redis connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis pool: {e}")
            _redis_conn = None
    return _redis_conn


def get_db_engine():
    """Get or create SQLAlchemy engine."""
    global _db_engine
    database_url = os.getenv("DATABASE_URL")
    if _db_engine is None and database_url:
        try:
            from sqlalchemy import create_engine
            _db_engine = create_engine(database_url, echo=False, pool_pre_ping=True)
            logger.debug("Database engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            _db_engine = None
    return _db_engine


def check_postgres() -> dict:
    """Check PostgreSQL connectivity with timeout."""
    database_url = os.getenv("DATABASE_URL")
    environment = os.getenv("ENVIRONMENT", "development")
    
    if not database_url:
        return {"status": "skipped", "reason": "DATABASE_URL not configured"}
    
    try:
        from sqlalchemy import text
        engine = get_db_engine()
        if not engine:
            return {"status": "error", "reason": "Failed to initialize database engine"}
        
        # Set connection timeout to 5 seconds
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.debug("PostgreSQL health check passed")
        return {"status": "ok"}
    
    except Exception as e:
        logger.warning(f"PostgreSQL health check failed: {e}")
        detail = str(e) if environment != "production" else "Database unavailable"
        return {"status": "error", "detail": detail}


def check_redis() -> dict:
    """Check Redis connectivity with timeout."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    environment = os.getenv("ENVIRONMENT", "development")
    
    if not redis_url:
        return {"status": "skipped", "reason": "REDIS_URL not configured"}
    
    try:
        r = get_redis_conn()
        if not r:
            return {"status": "error", "reason": "Failed to initialize Redis connection"}
        
        r.ping()
        logger.debug("Redis health check passed")
        return {"status": "ok"}
    
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        detail = str(e) if environment != "production" else "Redis unavailable"
        return {"status": "error", "detail": detail}


def check_ollama() -> dict:
    """Check Ollama service and required models."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    environment = os.getenv("ENVIRONMENT", "development")
    
    try:
        # Check service availability
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{ollama_url}/api/tags")
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
        
        # Check required models
        required = ["mistral-nemo:latest", "nomic-embed-text:latest"]
        missing = [m for m in required if m not in models]
        
        if missing:
            logger.warning(f"Ollama missing models: {missing}")
            return {"status": "degraded", "missing_models": missing, "available": models}
        
        logger.debug("Ollama health check passed")
        return {"status": "ok", "models": len(models)}
    
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
        detail = str(e) if environment != "production" else "Ollama unavailable"
        return {"status": "error", "detail": detail}


@router.get("/live")
async def liveness():
    """Kubernetes liveness probe: Is the app running?
    
    Returns 200 if app process is running.
    Fails if app is deadlocked or crashed.
    Should never check external dependencies (be fast, <100ms).
    """
    logger.debug("Liveness probe called")
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness():
    """Kubernetes readiness probe: Is the app ready to handle requests?
    
    Returns 200 if all critical services available.
    Returns 503 if critical service unavailable (e.g., Ollama down).
    Used by load balancers to route traffic.
    """
    logger.debug("Readiness probe called")
    
    # Ollama is critical (required for language detection and translation)
    ollama = check_ollama()
    
    # Optional services that shouldn't block readiness
    redis_status = check_redis()
    postgres = check_postgres()
    
    is_ready = ollama["status"] in ["ok", "degraded"]
    
    response = {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "critical_services": {
            "ollama": ollama,
        },
        "optional_services": {
            "redis": redis_status,
            "postgres": postgres,
        }
    }
    
    status_code = 200 if is_ready else 503
    return Response(
        content=json.dumps(response),
        status_code=status_code,
        media_type="application/json"
    )


@router.get("/")
async def health():
    """Full health status: Detailed service diagnostics.
    
    Returns 200 if all services healthy.
    Returns 503 if any service degraded or unhealthy.
    Includes detailed status for monitoring and debugging.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    logger.info("Full health check requested")
    
    postgres = check_postgres()
    redis_status = check_redis()
    ollama = check_ollama()

    # Overall status: ok only if all services ok
    statuses = [postgres, redis_status, ollama]
    has_error = any(s["status"] == "error" for s in statuses)
    has_degraded = any(s["status"] == "degraded" for s in statuses)
    
    if has_error:
        overall_status = "unhealthy"
        http_status = 503
    elif has_degraded:
        overall_status = "degraded"
        http_status = 200  # Still 200 but indicates degradation
    else:
        overall_status = "healthy"
        http_status = 200

    response = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "services": {
            "postgres": postgres,
            "redis": redis_status,
            "ollama": ollama,
        }
    }
    
    logger.info(f"Health check complete: {overall_status}")
    
    return Response(
        content=json.dumps(response),
        status_code=http_status,
        media_type="application/json"
    )