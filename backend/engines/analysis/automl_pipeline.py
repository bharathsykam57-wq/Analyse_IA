"""Custom AutoML-style classification pipeline using scikit-learn, Optuna and LightGBM.

This module is designed for production integration (e.g., FastAPI services) and avoids
PyCaret/Sktime dependency conflicts while remaining compatible with scikit-learn 1.5+.

Public functions:
- get_preprocessing_pipeline
- objective
- train_best_model
- generate_shap_explanation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import optuna
import pandas as pd
import shap
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass(frozen=True)
class AutoMLConfig:
    random_state: int = 42
    cv_splits: int = 5
    n_trials: int = 30


def _ensure_dataframe(X: pd.DataFrame | np.ndarray) -> pd.DataFrame:
    if isinstance(X, pd.DataFrame):
        return X.copy()
    return pd.DataFrame(X, columns=[f"feature_{i}" for i in range(X.shape[1])])


def _to_series(y: pd.Series | np.ndarray) -> pd.Series:
    if isinstance(y, pd.Series):
        return y.reset_index(drop=True)
    return pd.Series(y, name="target")


def get_preprocessing_pipeline(X: pd.DataFrame) -> ColumnTransformer:
    """Build preprocessing pipeline for mixed tabular data.

    - Numeric features: median imputation + standard scaling
    - Categorical features: most-frequent imputation + one-hot encoding
    """
    X_df = _ensure_dataframe(X)

    numeric_features = X_df.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_features = [col for col in X_df.columns if col not in numeric_features]

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

    return preprocessor


def objective(
    trial: optuna.trial.Trial,
    X: pd.DataFrame,
    y: pd.Series | np.ndarray,
    config: AutoMLConfig = AutoMLConfig(),
) -> float:
    """Optuna objective selecting/tuning RF, LightGBM, XGBoost, or Logistic Regression."""
    X_df = _ensure_dataframe(X)
    y_series = _to_series(y)

    model_name = trial.suggest_categorical(
        "model_name",
        ["random_forest", "lightgbm", "xgboost", "logistic_regression"],
    )

    if model_name == "random_forest":
        estimator = RandomForestClassifier(
            n_estimators=trial.suggest_int("rf_n_estimators", 100, 800),
            max_depth=trial.suggest_int("rf_max_depth", 3, 30),
            random_state=config.random_state,
            n_jobs=-1,
        )
    elif model_name == "lightgbm":
        estimator = LGBMClassifier(
            learning_rate=trial.suggest_float("lgbm_learning_rate", 0.005, 0.3, log=True),
            n_estimators=trial.suggest_int("lgbm_n_estimators", 100, 1200),
            random_state=config.random_state,
            n_jobs=-1,
            verbosity=-1,
        )
    elif model_name == "xgboost":
        estimator = XGBClassifier(
            n_estimators=trial.suggest_int("xgb_n_estimators", 100, 1000),
            max_depth=trial.suggest_int("xgb_max_depth", 3, 10),
            learning_rate=trial.suggest_float("xgb_learning_rate", 0.01, 0.3),
            random_state=config.random_state,
            n_jobs=-1,
            eval_metric="mlogloss",
        )
    else:
        estimator = LogisticRegression(
            C=trial.suggest_float("lr_c", 0.001, 10.0, log=True),
            max_iter=2000,
            random_state=config.random_state,
        )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", get_preprocessing_pipeline(X_df)),
            ("model", estimator),
        ]
    )

    cv = StratifiedKFold(n_splits=config.cv_splits, shuffle=True, random_state=config.random_state)
    scores = cross_val_score(pipeline, X_df, y_series, cv=cv, scoring="accuracy", n_jobs=-1)
    return float(np.mean(scores))


def _build_estimator_from_best_params(
    best_params: dict[str, Any],
    random_state: int,
) -> RandomForestClassifier | LGBMClassifier | XGBClassifier | LogisticRegression:
    model_name = str(best_params.get("model_name", "")).lower()

    if model_name == "random_forest":
        return RandomForestClassifier(
            n_estimators=int(best_params["rf_n_estimators"]),
            max_depth=int(best_params["rf_max_depth"]),
            random_state=random_state,
            n_jobs=-1,
        )

    if model_name == "lightgbm":
        return LGBMClassifier(
            learning_rate=float(best_params["lgbm_learning_rate"]),
            n_estimators=int(best_params["lgbm_n_estimators"]),
            random_state=random_state,
            n_jobs=-1,
            verbosity=-1,
        )

    if model_name == "xgboost":
        return XGBClassifier(
            n_estimators=int(best_params["xgb_n_estimators"]),
            max_depth=int(best_params["xgb_max_depth"]),
            learning_rate=float(best_params["xgb_learning_rate"]),
            random_state=random_state,
            n_jobs=-1,
            eval_metric="mlogloss",
        )

    if model_name == "logistic_regression":
        return LogisticRegression(
            C=float(best_params["lr_c"]),
            max_iter=2000,
            random_state=random_state,
        )

    raise ValueError(
        "best_params must include model_name as one of: "
        "'random_forest', 'lightgbm', 'xgboost', 'logistic_regression'"
    )


def train_best_model(
    X: pd.DataFrame,
    y: pd.Series | np.ndarray,
    best_params: dict[str, Any],
    random_state: int = 42,
) -> Pipeline:
    """Train final best model pipeline from Optuna best params."""
    X_df = _ensure_dataframe(X)
    y_series = _to_series(y)

    preprocessor = get_preprocessing_pipeline(X_df)
    estimator = _build_estimator_from_best_params(best_params, random_state=random_state)

    final_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", estimator),
        ]
    )

    final_pipeline.fit(X_df, y_series)
    return final_pipeline


def generate_shap_explanation(
    model_pipeline: Pipeline,
    X: pd.DataFrame,
    max_samples: int = 500,
) -> pd.DataFrame:
    """Generate SHAP feature-importance dataframe for trained final pipeline.

    Returns columns:
    - feature
    - importance (mean absolute SHAP value)
    sorted descending.
    """
    X_df = _ensure_dataframe(X)
    X_eval = X_df.head(max_samples).copy()

    preprocessor = model_pipeline.named_steps["preprocessor"]
    estimator = model_pipeline.named_steps["model"]

    X_transformed = preprocessor.transform(X_eval)
    feature_names = preprocessor.get_feature_names_out().tolist()

    explainer = shap.TreeExplainer(estimator)
    shap_values = explainer.shap_values(X_transformed)

    if isinstance(shap_values, list):
        values = np.mean([np.abs(v) for v in shap_values], axis=0)
    else:
        values = np.abs(shap_values)
        if values.ndim == 3:
            values = np.mean(values, axis=2)

    importance = np.mean(values, axis=0)

    explanation_df = pd.DataFrame(
        {
            "feature": feature_names,
            "importance": importance,
        }
    ).sort_values("importance", ascending=False, ignore_index=True)

    return explanation_df


def _run_demo() -> None:
    from sklearn.datasets import load_wine
    from sklearn.model_selection import train_test_split

    config = AutoMLConfig(random_state=42, cv_splits=5, n_trials=20)

    dataset = load_wine(as_frame=True)
    X_all = dataset.data
    y_all = dataset.target

    X_train, X_test, y_train, y_test = train_test_split(
        X_all,
        y_all,
        test_size=0.2,
        random_state=config.random_state,
        stratify=y_all,
    )

    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, X_train, y_train, config=config), n_trials=config.n_trials)

    best_pipeline = train_best_model(X_train, y_train, best_params=study.best_params, random_state=config.random_state)

    y_pred = best_pipeline.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)

    shap_df = generate_shap_explanation(best_pipeline, X_train, max_samples=200)

    print("=== AutoML Demo (Wine) ===")
    print(f"Best params: {study.best_params}")
    print(f"Best CV accuracy: {study.best_value:.4f}")
    print(f"Test accuracy: {test_acc:.4f}")
    print("Top SHAP features:")
    print(shap_df.head(10).to_string(index=False))


def run_automl(X: pd.DataFrame, y: pd.Series | np.ndarray, n_trials: int = 30) -> dict:
    """
    Industry-standard wrapper that encapsulates the full AutoML flow.
    Ensures the Celery worker has a single, stable entry point.
    """
    config = AutoMLConfig(n_trials=n_trials)
    
    # 1. Optimize hyperparameters
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, X, y, config=config), n_trials=config.n_trials)
    
    # 2. Train the production-ready model
    best_pipeline = train_best_model(X, y, best_params=study.best_params)
    
    # 3. Generate XAI (Explainable AI) metrics
    shap_df = generate_shap_explanation(best_pipeline, X)
    
    return {
        "best_params": study.best_params,
        "best_score": study.best_value,
        "feature_importance": shap_df.to_dict(orient="records"),
        "model": best_pipeline
    }

if __name__ == "__main__":
    _run_demo()
