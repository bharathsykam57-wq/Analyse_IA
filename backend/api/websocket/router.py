"""WebSocket endpoint for real-time task progress streaming.

Bridges authenticated clients to Redis pub/sub task progress updates.
Clients connect via JWT token and subscribe to task:{task_id} channel.

Endpoint: ws://host/ws/{task_id}?token={jwt}

Flow:
  1. Client connects with JWT token (query parameter)
  2. Validate token and register connection
  3. Check if task already completed (return immediately if done)
  4. Stream progress updates from Redis to WebSocket
  5. Auto-close on terminal status (completed/failed) or disconnect
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.api.websocket.manager import manager
from backend.api.auth.service import decode_access_token
from backend.api.celery.worker import celery_app
from celery.result import AsyncResult
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
):
    """Handle WebSocket connection for task progress streaming.
    
    Authenticates via JWT, checks task status, and streams real-time
    progress updates from Redis pub/sub to the WebSocket client.
    
    Args:
        websocket: FastAPI WebSocket connection
        task_id: Celery task UUID to subscribe to
        token: JWT access token (query parameter: ?token=...)
               Example: ws://localhost:8000/ws/abc123?token=eyJ0...
    
    Connection Lifecycle:
        1. Accept and register connection
        2. Validate JWT token (close 4001 if invalid)
        3. Check if task already completed (return result immediately)
        4. Subscribe to Redis channel and stream progress
        5. Close on terminal status or client disconnect
    
    Message Format:
        {
            "status": "started|processing|completed|failed|error",
            "task_id": "...",
            "message": "...",
            "result": {...},  # On success
            "error": "...",   # On failure
        }
    
    Error Handling:
        - 4001 close code: Invalid/expired token
        - Graceful disconnect: Connection lost handled by try/finally
        - Server errors: Logged and sent to client
    """
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001, reason="Token invalide")
        return

    await manager.connect(task_id, websocket)

    try:
        result = AsyncResult(task_id, app=celery_app)

        if result.status == "SUCCESS":
            await websocket.send_json({
                "status": "completed",
                "task_id": task_id,
                "result": result.result,
            })
            return

        if result.status == "FAILURE":
            await websocket.send_json({
                "status": "failed",
                "task_id": task_id,
                "error": str(result.result),
            })
            return

        await manager.stream_task(task_id, websocket)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: task_id={task_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"status": "error", "detail": str(e)})
        except Exception:
            pass
    finally:
        manager.disconnect(task_id)