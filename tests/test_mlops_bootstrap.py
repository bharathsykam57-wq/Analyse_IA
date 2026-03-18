"""Smoke checks for MLops bootstrap components (health + drift utility)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.monitoring.health import full_health_check
from scripts.check_data_drift import build_baseline_profile, compare_against_baseline


def main() -> int:
    # 1) Health includes mlflow/langfuse keys.
    health = asyncio.run(full_health_check())
    checks = health.get("checks", {})
    required = {"redis", "ollama", "langfuse", "mlflow"}
    missing = required - set(checks.keys())
    if missing:
        print(f"FAIL: missing health check keys: {missing}")
        return 1

    # 2) Drift utility baseline/check smoke.
    base_df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [10, 11, 12, 13, 14]})
    cur_df = pd.DataFrame({"x": [1, 2, 2, 4, 5], "y": [10, 11, 12, 13, 15]})

    baseline = build_baseline_profile(base_df)
    result = compare_against_baseline(cur_df, baseline, alpha=0.001)

    if "drift_detected" not in result or "columns" not in result:
        print("FAIL: invalid drift result shape")
        return 1

    print("PASS: mlops bootstrap smoke checks passed")
    print(json.dumps({
        "health_status": health.get("status"),
        "mlflow_status": checks.get("mlflow", {}).get("status"),
        "langfuse_status": checks.get("langfuse", {}).get("status"),
        "drift_detected": result.get("drift_detected"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
