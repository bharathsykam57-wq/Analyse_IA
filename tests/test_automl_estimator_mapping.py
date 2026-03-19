"""Unit checks for AutoML estimator mapping from Optuna best params."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from backend.engines.analysis.automl_pipeline import _build_estimator_from_best_params


def main() -> int:
    rf = _build_estimator_from_best_params(
        {
            "model_name": "random_forest",
            "rf_n_estimators": 123,
            "rf_max_depth": 7,
        },
        random_state=42,
    )
    if not isinstance(rf, RandomForestClassifier):
        print("FAIL: random_forest did not map to RandomForestClassifier")
        return 1

    lgbm = _build_estimator_from_best_params(
        {
            "model_name": "lightgbm",
            "lgbm_n_estimators": 200,
            "lgbm_learning_rate": 0.05,
        },
        random_state=42,
    )
    if not isinstance(lgbm, LGBMClassifier):
        print("FAIL: lightgbm did not map to LGBMClassifier")
        return 1

    xgb = _build_estimator_from_best_params(
        {
            "model_name": "xgboost",
            "xgb_n_estimators": 250,
            "xgb_max_depth": 6,
            "xgb_learning_rate": 0.07,
        },
        random_state=42,
    )
    if not isinstance(xgb, XGBClassifier):
        print("FAIL: xgboost did not map to XGBClassifier")
        return 1

    lr = _build_estimator_from_best_params(
        {
            "model_name": "logistic_regression",
            "lr_c": 1.5,
        },
        random_state=42,
    )
    if not isinstance(lr, LogisticRegression):
        print("FAIL: logistic_regression did not map to LogisticRegression")
        return 1

    try:
        _build_estimator_from_best_params({"model_name": "unknown"}, random_state=42)
        print("FAIL: unknown model_name should raise ValueError")
        return 1
    except ValueError:
        pass

    print("PASS: automl estimator mapping checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
