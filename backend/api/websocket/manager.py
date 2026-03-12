"""WebSocket connection manager for real-time task progress streaming.

Bridges Celery task progress (published to Redis) with WebSocket clients.
Each client subscribes to a task-specific Redis channel and receives
real-time updates (started → processing → completed/failed).

Architecture:
  Celery Worker: publish_progress() → Redis channel (task:{task_id})
  WebSocket: stream_task() → subscribe & listen → send to client
  Client: ws://host/ws/tasks/{task_id} → receive JSON updates

Usage:
  manager = ConnectionManager()
  await manager.connect(task_id, websocket)  # Handshake
  await manager.stream_task(task_id, websocket)  # Subscribe to Redis
"""

import asyncio
import json
import logging
import redis.asyncio as aioredis
import os

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class ConnectionManager:
    """Manages active WebSocket connections and Redis pub/sub subscriptions.
    
    Maintains a registry of connected clients per task_id and handles
    streaming of progress updates from Redis channels to WebSocket clients.
    Automatically cleans up connections on disconnect or completion.
    
    Attributes:
        active_connections: dict mapping task_id → websocket for active streams
    """

    def __init__(self):
        self.active_connections: dict = {}

    async def connect(self, task_id: str, websocket):
        """Accept WebSocket connection and register in active connections.
        
        Called when client connects to /ws/tasks/{task_id}.
        Stores connection for broadcast operations.
        
        Args:
            task_id: Celery task UUID
            websocket: FastAPI WebSocket connection
        """
        await websocket.accept()
        self.active_connections[task_id] = websocket
        logger.info(f"WebSocket connected: task_id={task_id}")

    def disconnect(self, task_id: str):
        """Remove connection from registry on client disconnect.
        
        Called when client closes WebSocket or connection is lost.
        
        Args:
            task_id: Celery task UUID
        """
        self.active_connections.pop(task_id, None)
        logger.info(f"WebSocket disconnected: task_id={task_id}")

    async def send(self, task_id: str, data: dict):
        """Send JSON message to WebSocket client (if connected).
        
        Gracefully handles dropped connections by cleaning up registry.
        
        Args:
            task_id: Celery task UUID
            data: JSON-serializable dict to send
        """
        ws = self.active_connections.get(task_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to {task_id}: {e}")
                self.disconnect(task_id)

    async def stream_task(self, task_id: str, websocket):
        """Subscribe to Redis channel and stream task progress to WebSocket.
        
        Long-lived connection that listens to Redis pub/sub channel
        matching pattern `task:{task_id}`. Forwards each progress update
        as JSON to the WebSocket client. Closes when task completes/fails.
        
        Flow:
            1. Connect to Redis
            2. Subscribe to task:{task_id} channel
            3. Listen for published progress updates (from Celery worker)
            4. Forward each update as JSON to WebSocket
            5. Close on terminal status (completed/failed)
        
        Args:
            task_id: Celery task UUID (matches Redis channel pattern)
            websocket: Active FastAPI WebSocket to stream to
        
        Progress Message Format:
            {
                "status": "started|processing|completed|failed",
                "task_id": "...",
                "message": "...",  # Bilingual (fr/en)
                "result": {...}  # Only on completion
                "error": "...",  # Only on failure
            }
        """
        r = aioredis.from_url(REDIS_URL)
        pubsub = r.pubsub()
        channel = f"task:{task_id}"

        await pubsub.subscribe(channel)
        logger.info(f"Subscribed to Redis channel: {channel}")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data = json.loads(message["data"])
                await websocket.send_json(data)
                logger.debug(f"Streamed to {task_id}: {data.get('status')}")

                if data.get("status") in ("completed", "failed"):
                    break

        except Exception as e:
            logger.error(f"WebSocket stream error for {task_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            await r.aclose()


manager = ConnectionManager()