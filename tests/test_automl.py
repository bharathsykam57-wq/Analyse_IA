"""Automated smoke test for custom AutoML pipeline."""

from __future__ import annotations

import os
import sys

import numpy as np
import optuna
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.analysis.automl_pipeline import (
    AutoMLConfig,
    objective,
    train_best_model,
    generate_shap_explanation,
)


def main() -> int:
    np.random.seed(7)
    n = 260

    X = pd.DataFrame(
        {
            "a": np.random.normal(0, 1, n),
            "b": np.random.normal(0, 1, n),
            "c": np.random.choice(["x", "y", "z"], n),
        }
    )

    logits = X["a"] * 1.4 + X["b"] * -0.9 + (X["c"] == "x").astype(int) * 0.8
    y = (logits + np.random.normal(0, 0.35, n) > 0).astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=7, stratify=y
    )

    config = AutoMLConfig(random_state=7, cv_splits=3, n_trials=6)
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, X_train, y_train, config), n_trials=config.n_trials)

    model = train_best_model(X_train, y_train, best_params=study.best_params, random_state=7)
    acc = float((model.predict(X_test) == y_test).mean())

    shap_df = generate_shap_explanation(model, X_train, max_samples=80)

    if shap_df.empty:
        print("FAIL: SHAP output is empty")
        return 1

    if acc < 0.65:
        print(f"FAIL: low test accuracy {acc:.4f}")
        return 1

    print("PASS: custom automl test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
