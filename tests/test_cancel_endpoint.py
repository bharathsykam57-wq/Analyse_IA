"""Cancellation endpoint smoke checks."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.api.main import app
import backend.api.routes.agent as agent_module
from backend.api.auth.router import get_current_active_user


class _DummyUser:
    def __init__(self):
        self.id = "test-user-id"
        self.email = "cancel-test@example.com"
        self.preferred_language = "en"


class _DummyResult:
    status = "STARTED"

    def revoke(self, terminate=True, signal=None):
        self.revoked = True
        self.terminate = terminate
        self.signal = signal


def main() -> int:
    client = TestClient(app)

    original_async_result = agent_module.AsyncResult
    original_publish_progress = agent_module.publish_progress
    app.dependency_overrides[get_current_active_user] = lambda: _DummyUser()

    captured = {"payload": None, "revoke_called": False}

    def _fake_async_result(task_id, app=None):
        obj = _DummyResult()
        original_revoke = obj.revoke

        def _wrapped_revoke(*args, **kwargs):
            captured["revoke_called"] = True
            return original_revoke(*args, **kwargs)

        obj.revoke = _wrapped_revoke
        return obj

    def _fake_publish(task_id, payload):
        captured["payload"] = payload

    try:
        agent_module.AsyncResult = _fake_async_result
        agent_module.publish_progress = _fake_publish

        response = client.post("/api/v1/agent/cancel/task-123")
        if response.status_code != 200:
            print(f"FAIL: expected 200 got {response.status_code} -> {response.text}")
            return 1

        body = response.json()
        if body.get("status") != "canceled":
            print("FAIL: unexpected cancel status")
            return 1

        if not captured["revoke_called"]:
            print("FAIL: revoke not called")
            return 1

        payload = captured["payload"] or {}
        if payload.get("status") != "canceled":
            print("FAIL: cancel progress payload status")
            return 1
        if payload.get("error_code") != "task_canceled":
            print("FAIL: cancel progress payload error_code")
            return 1

        print("PASS: cancel endpoint checks passed")
        return 0
    finally:
        agent_module.AsyncResult = original_async_result
        agent_module.publish_progress = original_publish_progress
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
