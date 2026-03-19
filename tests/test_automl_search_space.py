"""Regression checks for AutoML search space branches.

Ensures objective/train pipeline support all requested model branches:
- random_forest
- lightgbm
- xgboost
- logistic_regression
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.datasets import load_wine

from backend.engines.analysis.automl_pipeline import (
    AutoMLConfig,
    objective,
    train_best_model,
)


class _DummyTrial:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def suggest_categorical(self, name, choices):
        if name == "model_name":
            return self.model_name
        return choices[0]

    def suggest_int(self, name, low, high):
        mapping = {
            "rf_n_estimators": 120,
            "rf_max_depth": 6,
            "lgbm_n_estimators": 140,
            "xgb_n_estimators": 130,
            "xgb_max_depth": 5,
        }
        return int(mapping.get(name, low))

    def suggest_float(self, name, low, high, log=False):
        mapping = {
            "lgbm_learning_rate": 0.05,
            "xgb_learning_rate": 0.08,
            "lr_c": 1.0,
        }
        return float(mapping.get(name, low))


def main() -> int:
    data = load_wine(as_frame=True)
    X: pd.DataFrame = data.data
    y = data.target

    config = AutoMLConfig(random_state=42, cv_splits=3, n_trials=4)

    model_names = ["random_forest", "lightgbm", "xgboost", "logistic_regression"]
    scores: dict[str, float] = {}

    for model_name in model_names:
        score = objective(_DummyTrial(model_name), X, y, config=config)
        if not np.isfinite(score):
            print(f"FAIL: objective score is not finite for {model_name}")
            return 1
        scores[model_name] = float(score)

    best_model_name = max(scores, key=scores.get)
    params_by_model = {
        "random_forest": {
            "model_name": "random_forest",
            "rf_n_estimators": 120,
            "rf_max_depth": 6,
        },
        "lightgbm": {
            "model_name": "lightgbm",
            "lgbm_n_estimators": 140,
            "lgbm_learning_rate": 0.05,
        },
        "xgboost": {
            "model_name": "xgboost",
            "xgb_n_estimators": 130,
            "xgb_max_depth": 5,
            "xgb_learning_rate": 0.08,
        },
        "logistic_regression": {
            "model_name": "logistic_regression",
            "lr_c": 1.0,
        },
    }

    model = train_best_model(X, y, params_by_model[best_model_name], random_state=42)
    preds = model.predict(X.head(10))

    if np.asarray(preds).shape[0] != 10:
        print("FAIL: model prediction shape mismatch")
        return 1

    print("PASS: automl search space branch checks passed")
    print("scores:", {k: round(v, 4) for k, v in scores.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
