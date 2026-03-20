import logging
import os
from celery import Celery
from backend.utils.redis_config import get_redis_url  # Import your utility logic

# Initialize logger so it is defined for the manual fix below
logger = logging.getLogger(__name__)

# --- MANUAL FIX: Use the normalized URL for Upstash compatibility ---
celery_url = get_redis_url()

celery_app = Celery(
    "tasks",
    broker=celery_url,
    backend=celery_url,
    include=["backend.api.celery.tasks"]
)

# --- MANUAL FIX: Apply SSL/TLS settings for Cloud Redis (Upstash) ---
if celery_url.startswith("rediss://"):
    logger.info("Enabling SSL for Celery/Redis connection.")
    ssl_conf = {'ssl_cert_reqs': None}
    celery_app.conf.update(
        broker_use_ssl=ssl_conf,
        redis_backend_use_ssl=ssl_conf,
    )

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

if __name__ == "__main__":
    celery_app.start()