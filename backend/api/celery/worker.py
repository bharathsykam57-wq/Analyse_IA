from celery import Celery
from dotenv import load_dotenv
import os

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# SSL Configuration for Upstash Redis (rediss://)
# Using ssl_cert_reqs="CERT_NONE" for Upstash free tier compatibility
# In production, consider using CERT_REQUIRED with proper CA bundle
USE_REDIS_SSL = REDIS_URL.startswith("rediss://")
ssl_config = {
    "ssl_cert_reqs": "CERT_NONE",  # TODO: Switch to CERT_REQUIRED in production with CA bundle
    "ssl_check_hostname": False,    # Related to CERT_NONE; set to True with CERT_REQUIRED
} if USE_REDIS_SSL else {}

celery_app = Celery(
    "analyse_ia",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.api.celery.tasks"],
)

celery_app.conf.update(
    # SSL for Upstash Redis
    broker_use_ssl=ssl_config,
    redis_backend_use_ssl=ssl_config,

    # Broker connection retry (fixes Celery 6.0 deprecation warning)
    broker_connection_retry_on_startup=True,

    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="Europe/Paris",
    enable_utc=True,

    # Task Execution
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result Storage
    result_expires=3600,

    # Retry
    task_max_retries=3,
    task_default_retry_delay=5,

    # Task Routing
    task_routes={
        "backend.api.celery.tasks.run_analysis": {"queue": "analysis"},
        "backend.api.celery.tasks.run_rag": {"queue": "rag"},
        "backend.api.celery.tasks.run_agent": {"queue": "agent"},
    },
)