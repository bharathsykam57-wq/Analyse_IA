"""Cached task history endpoint smoke checks."""

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
        self.id = "history-user-id"
        self.email = "history@example.com"
        self.preferred_language = "en"


class _FakeRedis:
    def __init__(self):
        self.store = {
            "user_task_history:history-user-id": [b"task-a", b"task-b"],
            "task_result:task-a": json.dumps({"status": "completed", "result": {"answer": "ok"}}).encode("utf-8"),
            "task_result:task-b": json.dumps({"status": "failed", "error": "boom"}).encode("utf-8"),
        }

    def lrange(self, key, start, end):
        items = self.store.get(key, [])
        if end < 0:
            return items[start:]
        return items[start : end + 1]

    def get(self, key):
        return self.store.get(key)


def main() -> int:
    client = TestClient(app)

    original_redis_from_url = agent_module.redis.from_url
    app.dependency_overrides[get_current_active_user] = lambda: _DummyUser()

    try:
        agent_module.redis.from_url = lambda *_args, **_kwargs: _FakeRedis()

        response = client.get("/api/v1/agent/history/cache?limit=5")
        if response.status_code != 200:
            print(f"FAIL: expected 200 got {response.status_code} -> {response.text}")
            return 1

        body = response.json()
        if body.get("count") != 2:
            print("FAIL: expected 2 cached items")
            return 1

        history = body.get("history", [])
        if len(history) != 2:
            print("FAIL: invalid history length")
            return 1

        first = history[0].get("payload", {})
        second = history[1].get("payload", {})
        if first.get("status") not in {"completed", "failed"}:
            print("FAIL: first payload status invalid")
            return 1
        if second.get("status") not in {"completed", "failed"}:
            print("FAIL: second payload status invalid")
            return 1

        print("PASS: cached history endpoint checks passed")
        return 0
    finally:
        agent_module.redis.from_url = original_redis_from_url
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
