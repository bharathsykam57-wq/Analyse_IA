"""Regression test for ops DLQ endpoint.

Validates:
- Unauthorized access returns 401
- Authorized access returns DLQ payload shape
- Redis failure returns 500

Usage:
    python tests/test_ops_dlq_endpoint.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.api.main import app
import backend.api.routes.health as health_router_module


def main() -> int:
    client = TestClient(app)

    original_ops_token = health_router_module.OPS_API_TOKEN
    original_redis_from_url = health_router_module.redis.from_url

    try:
        # Configure predictable auth token for test.
        health_router_module.OPS_API_TOKEN = "ops-test-token"

        # 1) Unauthorized
        r1 = client.get("/api/v1/ops/celery/dlq")
        if r1.status_code != 401:
            print(f"FAIL: expected 401, got {r1.status_code} -> {r1.text}")
            return 1

        # 2) Authorized + mocked Redis payload
        class _FakeRedis:
            def lrange(self, *_args, **_kwargs):
                return [
                    b'{"task_id":"t1","status":"failed","error":"boom"}',
                    b'{"task_id":"t2","status":"failed","error_code":"task_failed"}',
                ]

        health_router_module.redis.from_url = lambda *_args, **_kwargs: _FakeRedis()

        r2 = client.get(
            "/api/v1/ops/celery/dlq?limit=2",
            headers={"X-Ops-Token": "ops-test-token"},
        )
        if r2.status_code != 200:
            print(f"FAIL: expected 200, got {r2.status_code} -> {r2.text}")
            return 1

        data = r2.json()
        required_keys = {"status", "key", "count", "items"}
        if not required_keys.issubset(data.keys()):
            print(f"FAIL: missing keys in success response: {required_keys - set(data.keys())}")
            return 1
        if data.get("count") != 2:
            print(f"FAIL: expected count=2, got {data.get('count')}")
            return 1

        # 3) Authorized + Redis failure path -> 500
        def _raise_redis(*_args, **_kwargs):
            raise RuntimeError("redis unavailable")

        health_router_module.redis.from_url = _raise_redis

        r3 = client.get(
            "/api/v1/ops/celery/dlq?limit=5",
            headers={"X-Ops-Token": "ops-test-token"},
        )
        if r3.status_code != 500:
            print(f"FAIL: expected 500, got {r3.status_code} -> {r3.text}")
            return 1

        print("PASS: ops DLQ endpoint regression checks passed")
        return 0
    finally:
        health_router_module.OPS_API_TOKEN = original_ops_token
        health_router_module.redis.from_url = original_redis_from_url


if __name__ == "__main__":
    raise SystemExit(main())
