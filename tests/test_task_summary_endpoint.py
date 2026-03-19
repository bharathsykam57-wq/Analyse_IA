"""Task summary endpoint smoke checks."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.api.main import app
import backend.api.routes.agent as agent_module
from backend.api.auth.router import get_current_active_user


class _DummyUser:
    def __init__(self):
        self.id = "summary-user-id"
        self.email = "summary@example.com"
        self.preferred_language = "en"


class _FakeAsyncResult:
    def __init__(self, status: str, result=None):
        self.status = status
        self.result = result


class _FakeRedis:
    def __init__(self, payload: dict | None):
        self.payload = payload

    def get(self, key):
        if self.payload is None:
            return None
        return json.dumps(self.payload).encode("utf-8")


def main() -> int:
    client = TestClient(app)

    original_async_result = agent_module.AsyncResult
    original_redis_from_url = agent_module.redis.from_url
    app.dependency_overrides[get_current_active_user] = lambda: _DummyUser()

    try:
        # Case 1: running task without cache
        agent_module.AsyncResult = lambda *_args, **_kwargs: _FakeAsyncResult("STARTED")
        agent_module.redis.from_url = lambda *_args, **_kwargs: _FakeRedis(None)

        r1 = client.get("/api/v1/agent/task/task-run/summary")
        if r1.status_code != 200:
            print(f"FAIL: running summary status {r1.status_code}")
            return 1
        b1 = r1.json()
        if b1.get("status") != "started" or b1.get("source") != "celery" or b1.get("terminal") is not False:
            print("FAIL: running summary payload mismatch")
            return 1

        # Case 2: cache fallback while celery says pending
        cached = {
            "status": "completed",
            "result": {"answer": "ok"},
            "can_cancel": False,
            "progress_percent": 100,
        }
        agent_module.AsyncResult = lambda *_args, **_kwargs: _FakeAsyncResult("PENDING")
        agent_module.redis.from_url = lambda *_args, **_kwargs: _FakeRedis(cached)

        r2 = client.get("/api/v1/agent/task/task-cache/summary")
        if r2.status_code != 200:
            print(f"FAIL: cache summary status {r2.status_code}")
            return 1
        b2 = r2.json()
        if b2.get("status") != "completed" or b2.get("source") != "cache" or b2.get("terminal") is not True:
            print("FAIL: cache summary payload mismatch")
            return 1

        # Case 3: terminal celery success
        agent_module.AsyncResult = lambda *_args, **_kwargs: _FakeAsyncResult("SUCCESS", {"answer": "done"})
        agent_module.redis.from_url = lambda *_args, **_kwargs: _FakeRedis(None)

        r3 = client.get("/api/v1/agent/task/task-success/summary")
        if r3.status_code != 200:
            print(f"FAIL: success summary status {r3.status_code}")
            return 1
        b3 = r3.json()
        if b3.get("status") != "completed" or b3.get("source") != "celery" or b3.get("terminal") is not True:
            print("FAIL: success summary payload mismatch")
            return 1

        print("PASS: task summary endpoint checks passed")
        return 0
    finally:
        agent_module.AsyncResult = original_async_result
        agent_module.redis.from_url = original_redis_from_url
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
