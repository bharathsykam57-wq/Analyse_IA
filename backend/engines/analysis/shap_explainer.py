"""SHAP explainability engine for ML model interpretation and compliance.

This module provides transparent model explanations using SHAP (SHapley Additive exPlanations)
values to support regulatory transparency requirements.

ARCHITECTURE OVERVIEW:
1. RETRAIN PHASE: Takes best model from AutoML, retrains with clean sklearn pipeline
   using StandardScaler (numeric) and OrdinalEncoder (categorical)
2. SHAP PHASE: Computes SHAP values on retrained model for explanations

WHY RETRAIN:
- AutoML applies complex internal preprocessing that's hard to reverse
- Explicit sklearn encoding ensures SHAP receives correct data format
- Provides complete transparency of feature transformation pipeline

SHAP EXPLAINER SELECTION:
- TreeExplainer: Tree-based models (RandomForest, GradientBoosting) - fast
- LinearExplainer: Linear models (Ridge, Lasso) - instant

COMPLIANCE: Supports EU AI Act Article 13, GDPR Article 22, French RGPD transparency
"""
import logging
import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge, Lasso, ElasticNet
from sklearn.ensemble import (
    RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor,
    RandomForestClassifier, GradientBoostingClassifier, ExtraTreesClassifier
)

logger = logging.getLogger(__name__)


# Map PyCaret model names to sklearn classes
REGRESSION_MODELS = {
    'Ridge': Ridge,
    'Lasso': Lasso,
    'ElasticNet': ElasticNet,
    'RandomForestRegressor': RandomForestRegressor,
    'GradientBoostingRegressor': GradientBoostingRegressor,
    'ExtraTreesRegressor': ExtraTreesRegressor,
}

CLASSIFICATION_MODELS = {
    'RandomForestClassifier': RandomForestClassifier,
    'GradientBoostingClassifier': GradientBoostingClassifier,
    'ExtraTreesClassifier': ExtraTreesClassifier,
}


def build_clean_pipeline(model_name: str, problem_type: str,
                          numeric_cols: list, categorical_cols: list):
    """Build clean sklearn pipeline with explicit feature encoding.

    Constructs two-stage pipeline:
    1. PREPROCESSOR: StandardScaler (numeric) + OrdinalEncoder (categorical)
    2. MODEL: Selected algorithm (Ridge, RandomForest, GradientBoosting, etc)

    Pipeline ensures SHAP receives properly formatted data with explicit transformations.

    Args:
        model_name: Best model name from AutoML (e.g., 'RandomForestRegressor').
                   Defaults to Ridge/RandomForest if not in registry.
        problem_type: 'regression' or 'classification'.
        numeric_cols: Numeric column names (StandardScaler applied).
        categorical_cols: Categorical column names (OrdinalEncoder applied).

    Returns:
        Unfitted sklearn Pipeline ready to call fit(X, y).
    """
    # Pick model class — default to Ridge/RandomForest if not found in registry
    if problem_type == 'regression':
        model_class = REGRESSION_MODELS.get(model_name, Ridge)
    else:
        model_class = CLASSIFICATION_MODELS.get(model_name, RandomForestClassifier)

    logger.info(f"Building clean sklearn pipeline: {model_class.__name__}")

    # BUILD PREPROCESSOR: Apply different transformations per feature type
    # StandardScaler: Normalize numeric features to mean=0, std=1
    # OrdinalEncoder: Convert categorical to integers 0, 1, 2, ...
    preprocessor = ColumnTransformer(transformers=[
        ('num', StandardScaler(), numeric_cols),  # Numeric: normalize
        ('cat', OrdinalEncoder(handle_unknown='use_encoded_value',
                               unknown_value=-1), categorical_cols),  # Categorical: encode to integers
    ], remainder='drop')

    # ASSEMBLE PIPELINE: Chain preprocessor → model
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('model', model_class())
    ])

    return pipeline


def get_encoded_feature_names(numeric_cols: list, categorical_cols: list) -> list:
    """Get feature names in ColumnTransformer output order.

    ColumnTransformer outputs: numeric columns (after scaling) + categorical columns (encoded).
    This order must match SHAP values array dimension order.

    Args:
        numeric_cols: Numeric column names (unchanged after StandardScaler).
        categorical_cols: Categorical column names (now integers after OrdinalEncoder).

    Returns:
        Combined list with numeric first, then categorical.
    """
    return numeric_cols + categorical_cols


def explain_model(
    automl_result: dict,
    df: pd.DataFrame,
    target_column: str,
    max_samples: int = 200
) -> dict:
    """Generate comprehensive SHAP explanations for ML model predictions.

    Main entry point for model interpretability. Retrains best AutoML model using
    explicit sklearn encoding, then computes SHAP values for global importance
    and local sample explanations.

    WORKFLOW:
    STEP 1: Validate AutoML result, extract model and features
    STEP 2: Prepare data (remove missing targets, identify column types)
    STEP 3: Build clean sklearn pipeline with StandardScaler + OrdinalEncoder
    STEP 4: Retrain pipeline on full dataset
    STEP 5: Transform data to encoded features
    STEP 6: Select SHAP explainer (TreeExplainer vs LinearExplainer)
    STEP 7: Compute SHAP values for all samples (or sample if large)
    STEP 8: Calculate global feature importance (mean absolute SHAP)
    STEP 9: Generate local explanations for first 3 samples
    STEP 10: Return complete explanation package

    GLOBAL IMPORTANCE shows which features drive model predictions overall.
    LOCAL EXPLANATION shows why a specific prediction was made.
    Formula: prediction = baseline + sum(feature contributions)

    COMPLIANCE: EU AI Act Article 13, GDPR Article 22, French RGPD transparency

    Args:
        automl_result: Output from automl_pipeline.run_automl() containing:
                      'best_model_name', 'features_used', 'problem_type', 'error'
        df: Full DataFrame with features + target column.
        target_column: Target column name in df.
        max_samples: Max samples for SHAP (default 200).
                    50-100: quick, 200-500: production, 1000+: comprehensive.

    Returns:
        Dictionary with 'global_importance', 'local_explanations',
        'baseline_prediction', 'feature_names', 'model_name', 'error'.
        Never raises; errors returned in result['error'].
    """
    # Initialize result dict with default values
    result = {
        'global_importance': [],
        'local_explanations': [],
        'baseline_prediction': None,
        'feature_names': [],
        'model_name': None,
        'error': None
    }

    # STEP 1: Validate AutoML result before proceeding
    if automl_result.get('error'):
        result['error'] = f"AutoML error: {automl_result['error']}"
        return result

    features_used = automl_result.get('features_used', [])
    model_name = automl_result.get('best_model_name', 'Ridge')
    problem_type = automl_result.get('problem_type', 'regression')

    if not features_used:
        result['error'] = "No features found in AutoML result"
        return result

    try:
        # STEP 2: Prepare data - extract features and target
        X = df[features_used].copy()
        y = df[target_column].copy()

        # Remove samples with missing target (can't train on NaN labels)
        mask = y.notna()
        X = X[mask].reset_index(drop=True)
        y = y[mask].reset_index(drop=True)

        # Identify column types for appropriate preprocessing
        numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = X.select_dtypes(
            include=['object', 'category']
        ).columns.tolist()

        logger.info(
            f"Retrain data: {len(X)} rows | "
            f"{len(numeric_cols)} numeric | {len(categorical_cols)} categorical"
        )

        # STEP 3: Build clean sklearn pipeline with explicit encoding
        pipeline = build_clean_pipeline(
            model_name, problem_type, numeric_cols, categorical_cols
        )
        
        # STEP 4: Retrain model with explicit sklearn pipeline
        pipeline.fit(X, y)
        result['model_name'] = model_name
        logger.info(f"Model retrained: {model_name}")

        # STEP 5: Transform data through fitted preprocessing for SHAP
        X_encoded = pipeline.named_steps['preprocessor'].transform(X)
        feature_names = get_encoded_feature_names(numeric_cols, categorical_cols)
        X_encoded_df = pd.DataFrame(X_encoded, columns=feature_names)

        # Sample for performance on large datasets
        if len(X_encoded_df) > max_samples:
            X_sample = X_encoded_df.sample(n=max_samples, random_state=42)
            logger.info(f"Sampled {max_samples} for SHAP from {len(X_encoded_df)} total")
        else:
            X_sample = X_encoded_df

        logger.info(
            f"Computing SHAP: {len(X_sample)} samples, {len(feature_names)} features"
        )

        # STEP 6: Select SHAP explainer based on model type
        trained_model = pipeline.named_steps['model']
        model_lower = type(trained_model).__name__.lower()
        tree_keywords = ['forest', 'boosting', 'tree', 'xgb', 'lgbm']

        if any(kw in model_lower for kw in tree_keywords):
            explainer = shap.TreeExplainer(trained_model)
            logger.info("Using TreeExplainer (fast for tree models)")
        else:
            explainer = shap.LinearExplainer(
                trained_model,
                shap.maskers.Independent(X_sample)
            )
            logger.info("Using LinearExplainer (instant for linear models)")

        # STEP 7: Compute SHAP values (shape: n_samples x n_features)
        shap_values = explainer.shap_values(X_sample)

        # Handle multi-class classification: use positive class (index 1)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        # STEP 8: Calculate global feature importance
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        total = mean_abs_shap.sum()

        importance_list = []
        for i, feat in enumerate(feature_names):
            imp = float(mean_abs_shap[i])
            importance_list.append({
                'feature': feat,
                'importance': round(imp, 4),
                'importance_percentage': round(
                    imp / total * 100, 2
                ) if total > 0 else 0
            })
        importance_list.sort(key=lambda x: x['importance'], reverse=True)
        result['global_importance'] = importance_list

        # Baseline = average prediction = reference point for SHAP
        predictions = pipeline.predict(X)
        baseline = float(np.mean(predictions))
        result['baseline_prediction'] = round(baseline, 4)
        result['feature_names'] = feature_names

        # STEP 9: Generate local explanations for first 3 samples
        sample_predictions = pipeline.predict(
            X.iloc[:min(3, len(X_sample))]
        )
        for i in range(min(3, len(X_sample))):
            sample_shap = shap_values[i]
            contributions = []
            for j, feat in enumerate(feature_names):
                contributions.append({
                    'feature': feat,
                    'value': float(X_sample.iloc[i][feat]),
                    'shap_contribution': round(float(sample_shap[j]), 4),
                    'direction': 'positive' if sample_shap[j] > 0 else 'negative'
                })
            contributions.sort(
                key=lambda x: abs(x['shap_contribution']), reverse=True
            )
            result['local_explanations'].append({
                'prediction': round(float(sample_predictions[i]), 4),
                'baseline': round(baseline, 4),
                'contributions': contributions
            })

        logger.info(
            f"SHAP complete. Top feature: "
            f"{importance_list[0]['feature']} "
            f"({importance_list[0]['importance_percentage']}%)"
        )

        return result

    except Exception as e:
        error_msg = f"SHAP explanation failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        result['error'] = error_msg
        return result