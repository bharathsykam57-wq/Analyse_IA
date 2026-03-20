import logging
import os
from celery import Celery
from backend.utils.redis_config import get_redis_url

logger = logging.getLogger(__name__)

# 1. Get the base URL (e.g., rediss://default:pass@host:port/0)
raw_url = get_redis_url()

# 2. FIX: Celery 5.4+ requires ssl_cert_reqs to be PART of the URL string for rediss://
# We append it as a query parameter.
if raw_url.startswith("rediss://"):
    logger.info("Enabling SSL and appending required cert parameters to URL.")
    # If the URL already has parameters, use &, otherwise use ?
    separator = "&" if "?" in raw_url else "?"
    celery_url = f"{raw_url}{separator}ssl_cert_reqs=none"
else:
    celery_url = raw_url

celery_app = Celery(
    "tasks",
    broker=celery_url,
    backend=celery_url,
    include=["backend.api.celery.tasks"]
)

# 3. Maintain the extra SSL config block for backward compatibility/extra safety
if celery_url.startswith("rediss://"):
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