from celery import Celery
from dotenv import load_dotenv
import os
import ssl
from backend.utils.redis_config import get_redis_url

load_dotenv()

REDIS_URL = get_redis_url()

# SSL Configuration for Upstash Redis (rediss://)
# Default is secure certificate validation; set REDIS_SSL_INSECURE=true only for emergency fallback.
USE_REDIS_SSL = REDIS_URL.startswith("rediss://")
REDIS_SSL_INSECURE = os.getenv("REDIS_SSL_INSECURE", "false").lower() == "true"

if USE_REDIS_SSL:
    if REDIS_SSL_INSECURE:
        ssl_config = {
            "ssl_cert_reqs": ssl.CERT_NONE,
            "ssl_check_hostname": False,
        }
    else:
        ssl_config = {
            "ssl_cert_reqs": ssl.CERT_REQUIRED,
            "ssl_check_hostname": True,
        }
else:
    ssl_config = {}

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