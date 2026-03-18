"""Monitoring metrics smoke test.

Validates Prometheus-style metrics endpoint is exposed and populated
after basic API traffic.

Usage:
  python tests/test_monitoring_metrics.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.api.main import app


def main() -> int:
    client = TestClient(app)

    # Generate some baseline traffic.
    r1 = client.get("/")
    if r1.status_code != 200:
        print(f"FAIL: root request failed: {r1.status_code}")
        return 1

    r2 = client.get("/api/v1/health/live")
    if r2.status_code != 200:
        print(f"FAIL: health/live request failed: {r2.status_code}")
        return 1

    # Fetch metrics and validate core series presence.
    metrics = client.get("/api/v1/metrics")
    if metrics.status_code != 200:
        print(f"FAIL: metrics endpoint failed: {metrics.status_code}")
        return 1

    body = metrics.text

    required_snippets = [
        "# TYPE analyseia_http_requests_total counter",
        "# TYPE analyseia_http_request_duration_seconds histogram",
        "# TYPE analyseia_celery_task_events_total counter",
        "# TYPE analyseia_celery_task_duration_seconds histogram",
        'analyseia_http_requests_total{method="GET",path="/",status="200"}',
        'analyseia_http_requests_total{method="GET",path="/api/v1/health/live",status="200"}',
    ]

    missing = [snippet for snippet in required_snippets if snippet not in body]
    if missing:
        print("FAIL: metrics output missing expected snippets:")
        for snippet in missing:
            print(f"  - {snippet}")
        return 1

    print("PASS: monitoring metrics endpoint smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
