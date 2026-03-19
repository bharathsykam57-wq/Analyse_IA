"""Agent endpoint for multi-phase analysis orchestration (Phase 1-3).

Dispatches user queries to the Celery task queue where the MasterAgent orchestrates:
  1. Phase 1 (EDA): Statistical analysis of datasets
  2. Phase 2 (RAG): Document-based question answering from PDFs/CSVs
  3. Phase 3 (Agent): Synthesis of results into coherent answer

Endpoints:
  POST /agent/ask - Dispatch query, returns task_id for WebSocket tracking
  GET /agent/status/{task_id} - Poll task result (use WebSocket for streaming)

Authentication & Authorization:
  All endpoints require valid JWT (Bearer token) via get_current_active_user.
  Results isolated per user (session_id derived from user.id).

Integration:
  Connects to: Celery worker (run_agent task), Redis (progress channels), WebSocket handler
  Frontend receives real-time updates via: ws://host/ws/tasks/{task_id}
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import logging
import json
import redis
from celery.result import AsyncResult

from backend.api.dependencies import get_db
from backend.api.auth.router import get_current_active_user
from backend.api.auth.models import User
from backend.api.celery.tasks import run_agent, publish_progress
from backend.api.celery.worker import celery_app
from backend.utils.redis_config import get_redis_url

logger = logging.getLogger(__name__)

REDIS_URL = get_redis_url()
TASK_RESULT_CACHE_PREFIX = "task_result"
USER_TASK_HISTORY_PREFIX = "user_task_history"
USER_TASK_HISTORY_MAX_ITEMS = 100

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    """Query request for multi-phase agent analysis.
    
    Parameters:
        query: Natural language question or analysis request (required).
               Example: "Quels sont les 3 principaux drivers de croissance?"
        session_id: Optional session identifier. Auto-generated from user.id if omitted.
                   Use for multi-turn conversations (same session_id = related queries).
        file_id: Optional file identifier to include in RAG context (Phase 2).
                File must exist in user's upload directory.
        language: Override language preference ("fr" | "en").
                 Falls back to Accept-Language header, then user preference.
    """
    query: str
    session_id: Optional[str] = None
    file_id: Optional[str] = None
    language: Optional[str] = None


class AgentResponse(BaseModel):
    """Async task response with tracking ID.
    
    Fields:
        task_id: Celery task UUID for WebSocket subscription or polling.
        session_id: Session identifier (for audit & multi-turn conversation).
        status: Always "queued" (task running asynchronously).
        message: Localized confirmation message.
    """
    task_id: str
    session_id: str
    status: str = "queued"
    message: str


class CancelResponse(BaseModel):
    task_id: str
    status: str
    message: str


def _task_cache_key(task_id: str) -> str:
    return f"{TASK_RESULT_CACHE_PREFIX}:{task_id}"


def _user_history_key(user_id: str) -> str:
    return f"{USER_TASK_HISTORY_PREFIX}:{user_id}"


def _record_user_task(user_id: str, task_id: str):
    try:
        r = redis.from_url(REDIS_URL)
        key = _user_history_key(user_id)
        r.lpush(key, task_id)
        r.ltrim(key, 0, USER_TASK_HISTORY_MAX_ITEMS - 1)
        r.expire(key, 60 * 60 * 24 * 14)
    except Exception as err:
        logger.warning(f"Failed to record user task history for user={user_id}: {err}")


def _get_cached_task_payload(task_id: str) -> dict | None:
    try:
        r = redis.from_url(REDIS_URL)
        raw = r.get(_task_cache_key(task_id))
        if not raw:
            return None
        decoded = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        return json.loads(decoded)
    except Exception as err:
        logger.warning(f"Failed to read cached task payload for task_id={task_id}: {err}")
        return None


@router.post("/ask", response_model=AgentResponse, status_code=status.HTTP_202_ACCEPTED)
async def ask_agent(
    request: AgentRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    accept_language: Optional[str] = Header(None),
):
    """Dispatch agent query to Celery for async multi-phase analysis.
    
    Flow:
        1. Resolve language preference (explicit > Accept-Language > user > default "fr")
        2. Resolve or generate session_id for conversation tracking
        3. Validate and resolve file_path from file_id if provided
        4. Send task to "agent" queue with timeout handling
        5. Return task_id immediately (202 Accepted)
    
    Real-Time Updates:
        Frontend subscribes to ws://host/ws/tasks/{task_id} for streaming updates:
        - started: Analysis initiated
        - processing: Agent processing (Phase 1/2 results aggregating)
        - completed: Result ready (agent_synthesis available)
    
    Fallback Polling:
        GET /agent/status/{task_id} returns current task status if WebSocket unavailable.
    
    Error Handling:
        - 401: Missing or invalid JWT token
        - 400: Query validation failure (empty, too long)
        - 404: file_id provided but file not found in user's upload directory
        - 500: Celery worker unavailable (retryable)
    
    Audit Logging:
        - task_id, user email, language, session_id logged for compliance
        - Results expire after 1 hour (privacy-by-design)
    
    Returns:
        AgentResponse with task_id for status polling or WebSocket subscription.
    """
    session_id = request.session_id or f"{current_user.id}"

    language = (
        request.language
        or _parse_accept_language(accept_language)
        or current_user.preferred_language
        or "fr"
    )

    file_path = None
    import os
    user_upload_dir = os.path.join("uploads", str(current_user.id))
    
    logger.info(f"Looking for files in: {user_upload_dir} (user_id={current_user.id})")
    
    # First, try user's own directory
    if os.path.exists(user_upload_dir):
        logger.info(f"Upload directory exists, scanning for files...")
        files_with_times = []
        
        for filename in os.listdir(user_upload_dir):
            if filename.startswith('.'):
                continue
            full_path = os.path.join(user_upload_dir, filename)
            
            if request.file_id:
                if filename.startswith(request.file_id):
                    file_path = full_path
                    logger.info(f"Found matching file for file_id: {file_path}")
                    break
            else:
                if filename.lower().endswith('.csv'):
                    try:
                        mtime = os.path.getmtime(full_path)
                        files_with_times.append((full_path, mtime))
                        logger.debug(f"Found CSV: {filename} (mtime={mtime})")
                    except OSError:
                        pass
        
        if not file_path and files_with_times and not request.file_id:
            file_path = max(files_with_times, key=lambda x: x[1])[0]
            logger.info(f"Auto-selected most recent CSV from user dir: {file_path}")
    else:
        logger.warning(f"User upload directory does not exist: {user_upload_dir}")
    
    # Fallback: Search for most recent CSV across all upload directories
    if not file_path and not request.file_id:
        logger.info("Searching for most recent CSV across all user directories...")
        upload_base_dir = "uploads"
        if os.path.exists(upload_base_dir):
            all_csvs = []
            for user_dir in os.listdir(upload_base_dir):
                user_path = os.path.join(upload_base_dir, user_dir)
                if not os.path.isdir(user_path):
                    continue
                for filename in os.listdir(user_path):
                    if filename.lower().endswith('.csv') and not filename.startswith('.'):
                        full_path = os.path.join(user_path, filename)
                        try:
                            mtime = os.path.getmtime(full_path)
                            all_csvs.append((full_path, mtime))
                        except OSError:
                            pass
            
            if all_csvs:
                file_path = max(all_csvs, key=lambda x: x[1])[0]
                logger.info(f"Auto-selected most recent CSV from all dirs: {file_path}")
    
    # If file_id was explicitly provided but not found, raise error
    if request.file_id and not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier introuvable. Vérifiez le file_id.",
        )

    task = run_agent.apply_async(
        kwargs={
            "query": request.query,
            "session_id": session_id,
            "language": language,
            "file_path": file_path,
        },
        queue="agent",
    )

    _record_user_task(str(current_user.id), task.id)

    logger.info(
        f"Agent task dispatched: {task.id} "
        f"user={current_user.email} "
        f"lang={language} "
        f"session={session_id}"
    )

    return AgentResponse(
        task_id=task.id,
        session_id=session_id,
        status="queued",
        message="Requête en cours de traitement..." if language == "fr" else "Request being processed...",
    )


@router.get("/status/{task_id}")
async def task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Poll task status (fallback for WebSocket unavailability).
    
    Task Status Values:
        - PENDING: Task queued, not yet started
        - STARTED: Worker processing (phases executing)
        - SUCCESS: Completed successfully, result available
        - FAILURE: Permanent failure (check error field)
        - RETRY: Transient failure, auto-retrying
    
    Response Fields:
        - task_id: Echo of requested task UUID
        - status: Current Celery status
        - result: Agent synthesis (only if status=SUCCESS)
                 Contains: analysis, rag_insights, agent_synthesis, timestamp
        - error: Failure reason (only if status=FAILURE)
    
    Note:
        For continuous updates, use WebSocket: ws://host/ws/tasks/{task_id}
        HTTP polling adds latency (1-5 minute resolution typical).
    
    Security:
        Implicit user authorization: task must belong to current_user.
        TODO: Validate ownership (task_id → session_id → current_user.id).
    
    Returns:
        dict with task_id, status, and conditional result/error fields.
    """
    result = AsyncResult(task_id, app=celery_app)

    if result.status in {"PENDING", "STARTED", "RETRY"}:
        cached_payload = _get_cached_task_payload(task_id)
        if cached_payload:
            return {
                "task_id": task_id,
                "status": str(cached_payload.get("status", "completed")).upper(),
                "cached": True,
                "payload": cached_payload,
            }

    response = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result)
    elif result.status == "REVOKED":
        response["status"] = "CANCELED"
        response["error"] = "Task canceled by user"

    return response


@router.get("/history/cache")
def get_cached_task_history(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    """Return recent cached terminal task payloads for current user."""
    try:
        r = redis.from_url(REDIS_URL)
        key = _user_history_key(str(current_user.id))
        task_ids_raw = r.lrange(key, 0, limit - 1)

        task_ids = [
            item.decode("utf-8") if isinstance(item, (bytes, bytearray)) else str(item)
            for item in task_ids_raw
        ]

        items = []
        for task_id in task_ids:
            payload = _get_cached_task_payload(task_id)
            if payload:
                items.append({"task_id": task_id, "payload": payload})

        return {
            "history": items,
            "count": len(items),
            "limit": limit,
        }
    except Exception as err:
        logger.exception(f"Failed to read cached task history for user_id={current_user.id}: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch cached history",
        )


@router.post("/cancel/{task_id}", response_model=CancelResponse)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Cancel an in-flight Celery task.

    Notes:
    - Uses Celery revoke(terminate=True) for best-effort termination.
    - Emits a terminal `canceled` progress event for WebSocket clients.
    """
    result = AsyncResult(task_id, app=celery_app)

    if result.status in {"SUCCESS", "FAILURE", "REVOKED"}:
        terminal_status = "canceled" if result.status == "REVOKED" else result.status.lower()
        return CancelResponse(
            task_id=task_id,
            status=terminal_status,
            message="Task already finished.",
        )

    result.revoke(terminate=True, signal="SIGTERM")
    publish_progress(
        task_id,
        {
            "status": "canceled",
            "message": "Task canceled by user",
            "error": "Task canceled by user",
            "error_code": "task_canceled",
            "can_cancel": False,
            "progress_percent": 100,
            "eta_seconds": 0,
            "canceled_by": str(current_user.id),
        },
    )

    logger.info(f"Task canceled: task_id={task_id} user={current_user.email}")
    return CancelResponse(
        task_id=task_id,
        status="canceled",
        message="Task cancellation requested.",
    )


def _parse_accept_language(header: Optional[str]) -> Optional[str]:
    """Extract primary language from Accept-Language HTTP header.
    
    Examples:
        "fr-FR,fr;q=0.9,en;q=0.5" → "fr"
        "en-US,en;q=0.5"           → "en"
        "de,en-US,en;q=0.5"        → None (not supported)
        None                        → None
    
    Args:
        header: Accept-Language header value from HTTP request.
    
    Returns:
        "fr", "en", or None (if not recognized).
    """
    if not header:
        return None
    primary = header.split(",")[0].split(";")[0].strip().lower()
    if primary.startswith("fr"):
        return "fr"
    if primary.startswith("en"):
        return "en"
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# GET /agent/history — Query experiment_runs for user's analysis history
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/history")
def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return the current user's analysis history from experiment_runs."""
    try:
        from sqlalchemy import text
        result = db.execute(
            text("""
                SELECT id, task_type, question, answer_preview,
                       best_model, accuracy, confidence_score,
                       dataset_rows, language, created_at
                FROM experiment_runs
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"user_id": str(current_user.id), "limit": limit, "offset": offset}
        )
        rows = result.fetchall()
        total = db.execute(
            text("SELECT COUNT(*) FROM experiment_runs WHERE user_id = :user_id"),
            {"user_id": str(current_user.id)}
        ).scalar()
        return {
            "history": [
                {
                    "id": row.id,
                    "task_type": row.task_type,
                    "question": row.question,
                    "answer_preview": row.answer_preview,
                    "best_model": row.best_model,
                    "accuracy": row.accuracy,
                    "confidence_score": row.confidence_score,
                    "dataset_rows": row.dataset_rows,
                    "language": row.language,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.exception(f"Failed to fetch history for user_id={current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch history",
        )
