"""Ops rate-limit state endpoint smoke checks."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.api.main import app
import backend.api.routes.health as health_module


def main() -> int:
    client = TestClient(app)

    original_ops_token = health_module.OPS_API_TOKEN
    original_get_state = health_module.get_rate_limit_state

    try:
        health_module.OPS_API_TOKEN = "ops-rate-limit-token"
        health_module.get_rate_limit_state = lambda scope, identity, window_sec=60: {
            "key": f"rate_limit:{scope}:{identity}:{window_sec}",
            "count": 3,
            "ttl_sec": 25,
            "window_sec": window_sec,
        }

        unauth = client.get("/api/v1/ops/rate-limit/state?scope=auth_login:ip&identity=1.2.3.4")
        if unauth.status_code != 401:
            print(f"FAIL: expected 401 unauth, got {unauth.status_code}")
            return 1

        auth = client.get(
            "/api/v1/ops/rate-limit/state?scope=auth_login:ip&identity=1.2.3.4&window_sec=60",
            headers={"X-Ops-Token": "ops-rate-limit-token"},
        )
        if auth.status_code != 200:
            print(f"FAIL: expected 200 auth, got {auth.status_code} -> {auth.text}")
            return 1

        body = auth.json()
        if body.get("count") != 3 or body.get("ttl_sec") != 25:
            print("FAIL: unexpected rate-limit state payload")
            return 1

        print("PASS: ops rate-limit state endpoint checks passed")
        return 0
    finally:
        health_module.OPS_API_TOKEN = original_ops_token
        health_module.get_rate_limit_state = original_get_state


if __name__ == "__main__":
    raise SystemExit(main())
