"""Endpoint-level rate limiting smoke checks for auth and agent routes."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from backend.api.main import app
import backend.api.auth.router as auth_module
import backend.api.routes.agent as agent_module
from backend.api.auth.router import get_current_active_user


class _DummyUser:
    def __init__(self):
        self.id = "rate-limit-user"
        self.email = "ratelimit@example.com"
        self.preferred_language = "en"


class _DummyAuthUser:
    def __init__(self):
        self.id = "550e8400-e29b-41d4-a716-446655440000"
        self.email = "auth@example.com"
        self.full_name = "Auth User"
        self.is_active = True
        self.is_verified = False
        self.preferred_language = "fr"
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


class _DummyTask:
    def __init__(self, task_id: str):
        self.id = task_id


def main() -> int:
    client = TestClient(app)

    orig_login_user = auth_module.login_user
    orig_create_access = auth_module.create_access_token
    orig_create_refresh = auth_module.create_refresh_token
    orig_auth_rl = auth_module.enforce_ip_rate_limit
    orig_auth_analytics = auth_module.log_analytics_event_sync

    orig_agent_ip_rl = agent_module.enforce_ip_rate_limit
    orig_agent_user_rl = agent_module.enforce_user_rate_limit
    orig_apply_async = agent_module.run_agent.apply_async

    app.dependency_overrides[get_current_active_user] = lambda: _DummyUser()

    auth_calls = {"n": 0}
    agent_calls = {"n": 0}

    def _auth_rl(*args, **kwargs):
        auth_calls["n"] += 1
        if auth_calls["n"] > 1:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please retry in one minute.",
            )

    def _agent_rl(*args, **kwargs):
        agent_calls["n"] += 1
        if agent_calls["n"] > 2:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many analysis requests for this account. Please retry in one minute.",
            )

    try:
        auth_module.login_user = lambda req, db: _DummyAuthUser()
        auth_module.create_access_token = lambda user_id, email: ("token", 900)
        auth_module.create_refresh_token = lambda user_id, db: "refresh"
        auth_module.enforce_ip_rate_limit = _auth_rl
        auth_module.log_analytics_event_sync = lambda **kwargs: None

        # First login passes.
        ok_login = client.post(
            "/api/v1/auth/login",
            json={"email": "x@example.com", "password": "Password1"},
        )
        if ok_login.status_code != 200:
            print(f"FAIL: first login expected 200 got {ok_login.status_code}")
            return 1

        # Second login blocked.
        blocked_login = client.post(
            "/api/v1/auth/login",
            json={"email": "x@example.com", "password": "Password1"},
        )
        if blocked_login.status_code != 429:
            print(f"FAIL: second login expected 429 got {blocked_login.status_code}")
            return 1

        agent_module.enforce_ip_rate_limit = _agent_rl
        agent_module.enforce_user_rate_limit = _agent_rl
        agent_module.run_agent.apply_async = lambda **kwargs: _DummyTask("task-rate-limit")

        # First ask passes.
        ok_ask = client.post(
            "/api/v1/agent/ask",
            json={"query": "hello"},
        )
        if ok_ask.status_code != 202:
            print(f"FAIL: first ask expected 202 got {ok_ask.status_code} -> {ok_ask.text}")
            return 1

        # Second ask blocked by limiter.
        blocked_ask = client.post(
            "/api/v1/agent/ask",
            json={"query": "hello again"},
        )
        if blocked_ask.status_code != 429:
            print(f"FAIL: second ask expected 429 got {blocked_ask.status_code}")
            return 1

        print("PASS: rate limit endpoint checks passed")
        return 0
    finally:
        auth_module.login_user = orig_login_user
        auth_module.create_access_token = orig_create_access
        auth_module.create_refresh_token = orig_create_refresh
        auth_module.enforce_ip_rate_limit = orig_auth_rl
        auth_module.log_analytics_event_sync = orig_auth_analytics

        agent_module.enforce_ip_rate_limit = orig_agent_ip_rl
        agent_module.enforce_user_rate_limit = orig_agent_user_rl
        agent_module.run_agent.apply_async = orig_apply_async

        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
