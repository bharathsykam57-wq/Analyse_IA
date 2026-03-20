"""Smoke test for custom AutoML pipeline (sklearn + optuna + lightgbm)."""

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
    np.random.seed(42)
    n = 500

    X = pd.DataFrame(
        {
            "surface": np.random.normal(75, 25, n).astype(int).clip(20, 200),
            "nb_pieces": np.random.randint(1, 7, n),
            "annee_construction": np.random.randint(1950, 2023, n),
            "ville": np.random.choice(["Paris", "Lyon", "Marseille", "Bordeaux"], n),
            "type_bien": np.random.choice(["Appartement", "Maison"], n, p=[0.7, 0.3]),
        }
    )

    score_signal = (
        X["surface"] * 0.03
        + X["nb_pieces"] * 0.35
        + (X["ville"] == "Paris").astype(int) * 0.8
        + np.random.normal(0, 0.3, n)
    )
    y = (score_signal > np.median(score_signal)).astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    config = AutoMLConfig(random_state=42, cv_splits=3, n_trials=8)
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, X_train, y_train, config), n_trials=config.n_trials)

    final_model = train_best_model(X_train, y_train, best_params=study.best_params, random_state=42)
    acc = float((final_model.predict(X_test) == y_test).mean())
    shap_df = generate_shap_explanation(final_model, X_train, max_samples=120)

    print("=== Custom AutoML Smoke Test ===")
    print(f"Best params: {study.best_params}")
    print(f"Best CV score: {study.best_value:.4f}")
    print(f"Test accuracy: {acc:.4f}")
    print("Top SHAP features:")
    print(shap_df.head(5).to_string(index=False))

    if acc < 0.70:
        print("FAIL: Accuracy below expected threshold")
        return 1

    print("PASS: custom AutoML pipeline works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
