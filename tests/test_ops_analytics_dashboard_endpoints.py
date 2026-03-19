"""Ops analytics dashboard/upload endpoints smoke checks."""

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
    original_dashboard_fn = health_module.get_analytics_dashboard_cards_sync
    original_uploads_fn = health_module.get_upload_distribution_sync

    try:
        health_module.OPS_API_TOKEN = "ops-dashboard-token"
        health_module.get_analytics_dashboard_cards_sync = lambda days=7: {
            "window_days": days,
            "cards": {
                "signups": 2,
                "logins": 10,
                "uploads": 5,
                "analysis_requests": 7,
                "task_success_rate": 0.85,
                "analysis_avg_duration_ms": 1200.0,
            },
        }
        health_module.get_upload_distribution_sync = lambda days=7: {
            "window_days": days,
            "total_uploads": 5,
            "by_file_type": [
                {"file_type": "csv", "upload_count": 3, "total_bytes": 3000, "avg_size_bytes": 1000.0, "max_size_bytes": 1500},
                {"file_type": "pdf", "upload_count": 2, "total_bytes": 4000, "avg_size_bytes": 2000.0, "max_size_bytes": 2500},
            ],
        }

        unauth = client.get("/api/v1/ops/analytics/dashboard")
        if unauth.status_code != 401:
            print(f"FAIL: expected 401 for dashboard unauth, got {unauth.status_code}")
            return 1

        dashboard = client.get(
            "/api/v1/ops/analytics/dashboard?days=14",
            headers={"X-Ops-Token": "ops-dashboard-token"},
        )
        if dashboard.status_code != 200:
            print(f"FAIL: dashboard expected 200, got {dashboard.status_code} -> {dashboard.text}")
            return 1
        body_dash = dashboard.json()
        if body_dash.get("window_days") != 14:
            print("FAIL: dashboard days mismatch")
            return 1
        if "cards" not in body_dash or "logins" not in body_dash["cards"]:
            print("FAIL: dashboard payload shape mismatch")
            return 1

        uploads = client.get(
            "/api/v1/ops/analytics/uploads?days=30",
            headers={"X-Ops-Token": "ops-dashboard-token"},
        )
        if uploads.status_code != 200:
            print(f"FAIL: uploads expected 200, got {uploads.status_code} -> {uploads.text}")
            return 1
        body_upload = uploads.json()
        if body_upload.get("window_days") != 30:
            print("FAIL: uploads days mismatch")
            return 1
        if body_upload.get("total_uploads") != 5:
            print("FAIL: uploads total mismatch")
            return 1

        print("PASS: ops analytics dashboard/upload endpoint checks passed")
        return 0
    finally:
        health_module.OPS_API_TOKEN = original_ops_token
        health_module.get_analytics_dashboard_cards_sync = original_dashboard_fn
        health_module.get_upload_distribution_sync = original_uploads_fn


if __name__ == "__main__":
    raise SystemExit(main())
