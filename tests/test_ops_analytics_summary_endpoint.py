"""Ops analytics summary endpoint smoke checks."""

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
    original_summary_fn = health_module.get_analytics_summary_sync

    try:
        health_module.OPS_API_TOKEN = "ops-analytics-token"
        health_module.get_analytics_summary_sync = lambda days=7: {
            "window_days": days,
            "total_events": 10,
            "success_events": 8,
            "failure_events": 2,
            "success_rate": 0.8,
            "events_by_type": [
                {
                    "event_type": "user_login",
                    "total_count": 4,
                    "success_count": 3,
                    "failure_count": 1,
                    "avg_duration_ms": 120.0,
                }
            ],
        }

        unauth = client.get("/api/v1/ops/analytics/summary")
        if unauth.status_code != 401:
            print(f"FAIL: expected 401, got {unauth.status_code}")
            return 1

        auth = client.get(
            "/api/v1/ops/analytics/summary?days=14",
            headers={"X-Ops-Token": "ops-analytics-token"},
        )
        if auth.status_code != 200:
            print(f"FAIL: expected 200, got {auth.status_code} -> {auth.text}")
            return 1

        body = auth.json()
        if body.get("window_days") != 14:
            print("FAIL: days parameter not forwarded")
            return 1
        if body.get("total_events") != 10:
            print("FAIL: unexpected summary payload")
            return 1

        print("PASS: ops analytics summary endpoint checks passed")
        return 0
    finally:
        health_module.OPS_API_TOKEN = original_ops_token
        health_module.get_analytics_summary_sync = original_summary_fn


if __name__ == "__main__":
    raise SystemExit(main())
