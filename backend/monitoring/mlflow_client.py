"""Optional MLflow integration for experiment tracking.

This module is safe when MLflow isn't installed or configured.
Calls become no-ops and never raise to avoid impacting request/task flow.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


_MLFLOW_MODULE = None
_MLFLOW_ENABLED = None


def _load_mlflow():
    global _MLFLOW_MODULE, _MLFLOW_ENABLED
    if _MLFLOW_ENABLED is not None:
        return _MLFLOW_MODULE if _MLFLOW_ENABLED else None

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "").strip()
    if not tracking_uri:
        _MLFLOW_ENABLED = False
        return None

    try:
        import mlflow  # type: ignore

        mlflow.set_tracking_uri(tracking_uri)
        _MLFLOW_MODULE = mlflow
        _MLFLOW_ENABLED = True
        return _MLFLOW_MODULE
    except Exception as err:
        logger.warning(f"MLflow unavailable, disabled: {err}")
        _MLFLOW_ENABLED = False
        return None


def check_mlflow_status() -> dict[str, Any]:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "").strip()
    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "analyseia")

    if not tracking_uri:
        return {
            "status": "skipped",
            "reason": "MLFLOW_TRACKING_URI not configured",
        }

    mlflow = _load_mlflow()
    if mlflow is None:
        return {
            "status": "error",
            "tracking_uri": tracking_uri,
            "reason": "MLflow module unavailable or initialization failed",
        }

    try:
        mlflow.set_experiment(experiment_name)
        return {
            "status": "ok",
            "tracking_uri": tracking_uri,
            "experiment": experiment_name,
        }
    except Exception as err:
        return {
            "status": "error",
            "tracking_uri": tracking_uri,
            "experiment": experiment_name,
            "error": str(err),
        }


def log_mlflow_run(
    *,
    run_name: str,
    params: dict[str, Any] | None = None,
    metrics: dict[str, float] | None = None,
    tags: dict[str, str] | None = None,
) -> None:
    """Best-effort MLflow run logging. Never raises."""
    mlflow = _load_mlflow()
    if mlflow is None:
        return

    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "analyseia")

    try:
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=run_name):
            for key, value in (params or {}).items():
                mlflow.log_param(key, value)
            for key, value in (metrics or {}).items():
                if value is not None:
                    mlflow.log_metric(key, float(value))
            if tags:
                mlflow.set_tags(tags)
    except Exception as err:
        logger.warning(f"MLflow logging failed (non-blocking): {err}")
