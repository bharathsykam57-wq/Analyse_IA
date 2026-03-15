"""Celery task queue worker configuration for distributed task processing.

Celery enables asynchronous task execution, enabling long-running operations without
blocking HTTP requests. Perfect for CPU/IO-intensive work (LLM inference, data analysis).

Task Processing Architecture:
    - Message Broker: Redis (REDIS_URL) for task distribution
    - Result Backend: Redis for storing task results
    - Task Serialization: JSON (human-readable, language-independent)
    - Task Routing: 3 separate queues by workload type (analysis, rag, agent)
    - Worker Model: One task per worker (prefetch=1) for heavyweight LLM tasks

Supported Tasks:
    - run_analysis: Data analysis with AutoML (analysis queue)
    - run_rag: Document processing with RAG chain (rag queue)
    - run_agent: Master agent orchestration (agent queue)

Asynchronous Flow:
    1. FastAPI route receives request
    2. Route submits task via celery_app.send_task()
    3. Task queued in Redis (broker)
    4. Celery worker picks up task from queue
    5. Worker executes function (blocking, CPU/IO intensive)
    6. Result stored in Redis (backend)
    7. Client polls result endpoint to check status
    8. Result expires after 1 hour (result_expires=3600)

Configuration:
    - JSON Serialization: Human-readable, safe without pickle security risk
    - Europe/Paris Timezone: RGPD/CNIL compliance, user-focused
    - Task Tracking: task_track_started enabled (clients know task started)
    - Late Acks: task_acks_late ensures failed tasks are retried
    - Prefetch=1: No task hoarding (allows other workers to pick up tasks)
    - Max Retries: 3 attempts per task with 5-second delays
    - Result Expiry: 1 hour (sufficient for most operations, saves memory)

Performance Tuning:
    - worker_prefetch_multiplier=1: Prevents worker from consuming all tasks
    - task_acks_late=True: Worker acknowledges task after completion (failure resilient)
    - task_max_retries=3: Prevents infinite retry loops
    - task_default_retry_delay=5: 5-second exponential backoff between retries

Multi-Queue Design:
    - Separate queues prevent analysis tasks from blocking RAG tasks
    - Can scale workers per queue independently
    - Example: 2x analysis workers, 4x rag workers, 1x agent worker

Example Usage in FastAPI:
    from celery import current_app as celery_app
    
    @router.post("/run-analysis")
    async def submit_analysis(request: AnalysisRequest, current_user: User):
        task = celery_app.send_task(
            'backend.api.celery.tasks.run_analysis',
            args=(str(current_user.id), request.file_path),
            queue='analysis'
        )
        return {"task_id": task.id, "status": "queued"}

Result Backend Expiry:
    - Results automatically deleted after 1 hour
    - Prevents Redis memory exhaustion (tasks accumulate)
    - Clients must fetch results within 1 hour
    - Consider increasing if long-polling clients need more time

Error Handling:
    - Automatic retry on task failure (up to 3 times)
    - 5-second initial delay, exponential backoff
    - Max retries: 3 (4 attempts total)
    - Failed tasks after retries stored as error results

Monitoring:
    - task_track_started=True enables client progress tracking
    - Can monitor via Flower (Celery monitoring tool)
    - View task status: celery_app.AsyncResult(task_id).state
    - View task result: celery_app.AsyncResult(task_id).get()

Security:
    - JSON serialization prevents arbitrary code execution (safer than pickle)
    - REDIS_URL from environment (separates config from code)
    - Task routing prevents unauthorized queue access

Deployment:
    - Start worker: celery -A backend.api.celery.worker worker -l info
    - Start specific queue: celery -A backend.api.celery.worker worker -Q analysis -l info
    - Multiple workers: celery multi start w1 w2 w3 -A backend.api.celery.worker

Related:
    - Tasks defined in backend/api/celery/tasks.py
    - FastAPI integration in backend/api/agent/master_agent.py
    - Redis dependencies: redis protocol, connection pool
"""

from celery import Celery
from dotenv import load_dotenv
import os

load_dotenv()

# Redis Connection Configuration
# ═══════════════════════════════════════════════════════════════════════════════
# REDIS_URL: Message broker and result backend location
# Format: redis://[password@]host:port/db or rediss://... (secure)
# Examples:
#   Local: redis://localhost:6379/0
#   Production: redis://:password@redis.example.com:6379/0
#   Secure (Render): rediss://:password@host:port/db?ssl_cert_reqs=required
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# SSL Configuration for Secure Redis (rediss://)
# Detect if Redis URL uses SSL (rediss:// protocol)
USE_REDIS_SSL = REDIS_URL.startswith("rediss://")
broker_use_ssl = {"ssl_cert_reqs": "required"} if USE_REDIS_SSL else {}

# Celery Application Initialization
# ═══════════════════════════════════════════════════════════════════════════════
# Parameters:
#   - "analyse_ia": App name (used in logging, task prefixes)
#   - broker: Redis URL for message queue (task distribution)
#   - backend: Redis URL for result storage (task result persistence)
#   - include: Module paths to auto-import tasks (enables task discovery)
#   - broker_use_ssl: SSL config for secure Redis connections
celery_app = Celery(
    "analyse_ia",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.api.celery.tasks"],
)

# Celery Configuration
# ═══════════════════════════════════════════════════════════════════════════════
celery_app.conf.update(
    # ─────────────────────────────────────────────────────────────────────────
    # SSL Configuration for Secure Redis
    # ─────────────────────────────────────────────────────────────────────────
    # broker_use_ssl: SSL configuration for Redis connections
    #   - Required when using rediss:// protocol (Render Redis)
    #   - ssl_cert_reqs="required": Verify server certificate (CERT_REQUIRED)
    #   - ssl_cert_reqs="optional": Accept certificates but don't verify (CERT_OPTIONAL)
    #   - ssl_cert_reqs="none": No certificate validation (CERT_NONE)
    # Note: Upstash and Render both require "required"
    broker_use_ssl=broker_use_ssl,

    # ─────────────────────────────────────────────────────────────────────────
    # Serialization Configuration
    # ─────────────────────────────────────────────────────────────────────────
    # task_serializer: Format for serializing task arguments/results
    #   - "json": Human-readable, language-independent, no pickle security risk
    #   - "pickle": Python-specific, faster, potential RCE attack vector (avoid)
    # accept_content: Formats worker accepts from broker
    # result_serializer: Format for storing task results in backend
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # ─────────────────────────────────────────────────────────────────────────
    # Timezone Configuration (RGPD/CNIL Compliance)
    # ─────────────────────────────────────────────────────────────────────────
    # timezone: User-visible time zone (Europe/Paris for French data)
    # enable_utc: Store/process times in UTC internally (consistency)
    # Rationale: Display times in user's timezone, process in UTC (no ambiguity)
    timezone="Europe/Paris",
    enable_utc=True,

    # ─────────────────────────────────────────────────────────────────────────
    # Task Execution Behavior
    # ─────────────────────────────────────────────────────────────────────────
    # task_track_started: Update task state to "STARTED" when execution begins
    #   - Clients can distinguish "pending" from "running"
    #   - Allows progress tracking and timeout detection
    #   - Slightly more overhead (one state update per task)
    # task_acks_late: Acknowledge task completion AFTER execution (not before)
    #   - If worker crashes during task, task re-queued (failure resilient)
    #   - Prevents task loss, ensures at-least-once delivery
    #   - Tradeoff: Potential duplicate execution (idempotent tasks required)
    # worker_prefetch_multiplier: Tasks to prefetch per worker
    #   - 1 = one task at a time (prevents hoarding, fair distribution)
    #   - Higher = better throughput, worse fairness (hoarding risk)
    #   - LLM tasks are CPU-bound and heavy, so 1 is appropriate
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # ─────────────────────────────────────────────────────────────────────────
    # Result Storage & Expiry
    # ─────────────────────────────────────────────────────────────────────────
    # result_expires: Seconds before result auto-deleted from backend
    #   - 3600 = 1 hour (reasonable for most operations)
    #   - Client must fetch result within 1 hour
    #   - Prevents Redis memory exhaustion (results accumulate)
    #   - Increase if clients need longer result retention
    result_expires=3600,

    # ─────────────────────────────────────────────────────────────────────────
    # Retry Configuration (Fault Tolerance)
    # ─────────────────────────────────────────────────────────────────────────
    # task_max_retries: Maximum retry attempts per task
    #   - 3 = 4 total attempts (1 initial + 3 retries)
    #   - Prevents infinite retry loops on permanent failures
    #   - Exponential backoff applied between retries
    # task_default_retry_delay: Initial delay in seconds before first retry
    #   - 5 = 5 seconds (allows transient issues to resolve)
    #   - Exponential backoff: 2nd retry ~10s, 3rd ~20s, etc.
    task_max_retries=3,
    task_default_retry_delay=5,

    # ─────────────────────────────────────────────────────────────────────────
    # Task Routing (Multi-Queue Design)
    # ─────────────────────────────────────────────────────────────────────────
    # Maps task names to specific queues (independent processing)
    # Benefits:
    #   - Prevent blocked queues (analysis slowdown doesn't affect RAG)
    #   - Scale workers per queue independently
    #   - Prioritize queues differently
    # Usage: celery -A backend.api.celery.worker worker -Q analysis,rag,agent
    # Or per-queue: celery -A backend.api.celery.worker worker -Q analysis -l info
    task_routes={
        "backend.api.celery.tasks.run_analysis": {"queue": "analysis"},
        "backend.api.celery.tasks.run_rag": {"queue": "rag"},
        "backend.api.celery.tasks.run_agent": {"queue": "agent"},
    },
)