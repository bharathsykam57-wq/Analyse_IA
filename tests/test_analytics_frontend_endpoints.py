"""Frontend-facing analytics endpoints smoke checks."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.api.main import app
import backend.api.routes.analytics as analytics_module
from backend.api.auth.router import get_current_active_user


class _DummyUser:
    def __init__(self):
        self.id = "frontend-analytics-user"
        self.email = "frontend-analytics@example.com"
        self.preferred_language = "en"


def main() -> int:
    client = TestClient(app)

    original_overview = analytics_module.get_user_activity_overview_sync
    original_perf = analytics_module.get_analysis_performance_timeseries_sync
    app.dependency_overrides[get_current_active_user] = lambda: _DummyUser()

    try:
        analytics_module.get_user_activity_overview_sync = lambda user_id, days: {
            "window_days": days,
            "user_id": user_id,
            "cards": {
                "logins": 4,
                "uploads": 2,
                "analysis_requests": 3,
                "cancellations": 1,
                "total_upload_bytes": 999,
            },
            "events_by_type": [{"event_type": "user_login", "count": 4}],
        }
        analytics_module.get_analysis_performance_timeseries_sync = lambda days: {
            "window_days": days,
            "series": [
                {
                    "date": "2026-03-19",
                    "analysis_requests": 3,
                    "analysis_avg_duration_ms": 1234.0,
                    "task_executions": 3,
                    "task_success_rate": 0.66,
                }
            ],
        }

        overview = client.get("/api/v1/analytics/me/overview?days=14")
        if overview.status_code != 200:
            print(f"FAIL: overview expected 200 got {overview.status_code} -> {overview.text}")
            return 1
        body_overview = overview.json()
        if body_overview.get("window_days") != 14 or body_overview.get("cards", {}).get("logins") != 4:
            print("FAIL: overview payload mismatch")
            return 1

        perf = client.get("/api/v1/analytics/performance?days=30")
        if perf.status_code != 200:
            print(f"FAIL: performance expected 200 got {perf.status_code} -> {perf.text}")
            return 1
        body_perf = perf.json()
        if body_perf.get("window_days") != 30 or len(body_perf.get("series", [])) != 1:
            print("FAIL: performance payload mismatch")
            return 1

        print("PASS: frontend analytics endpoint checks passed")
        return 0
    finally:
        analytics_module.get_user_activity_overview_sync = original_overview
        analytics_module.get_analysis_performance_timeseries_sync = original_perf
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
