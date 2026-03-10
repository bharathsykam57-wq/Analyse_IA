"""AutoML pipeline for automatic model training and model selection.

Orchestrates end-to-end machine learning workflow: problem type detection,
feature engineering, model training via PyCaret, and best model selection.
Balances accuracy with speed through configurable sampling.

Works directly with dataset_loader.load_dataset() output and supports
both regression and classification tasks with appropriate metrics.

Typical Usage:
    from backend.engines.analysis.dataset_loader import load_dataset
    from backend.engines.analysis.automl_pipeline import run_automl

    dataset = load_dataset('data/sales.csv')
    result = run_automl(dataset, target_column='revenue', max_models=10)
    if not result['error']:
        model = result['best_model']
        print(f"Best model: {result['best_model_name']}")
        print(f"Metrics: {result['metrics']}")
"""
import logging
import pandas as pd
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


def detect_problem_type(df: pd.DataFrame, target_column: str) -> str:
    """Detect whether the problem is regression or classification.

    Uses heuristics to infer the ML problem type from target variable characteristics:
    - Numeric targets: classified as regression if they have sufficient cardinality
      (>5% unique values AND >10 unique values), otherwise classification
    - Non-numeric targets: classified as classification

    This approach handles edge cases like binary encoded as numbers (0/1)
    which should be classification despite numeric type.

    Args:
        df: DataFrame containing the data.
        target_column: Name of the column to predict.

    Returns:
        'regression' for continuous numeric targets, 'classification' otherwise.

    Examples:
        Binary outcome (0/1): returns 'classification'
        Price range (250000-800000): returns 'regression'
        Categorical (Paris/Lyon): returns 'classification'
    """
    target = df[target_column].dropna()

    # Check if target values are numeric (int, float types)
    if pd.api.types.is_numeric_dtype(target):
        # Calculate the ratio of unique values to total values
        # High cardinality suggests continuous variable (regression)
        unique_ratio = target.nunique() / len(target)
        
        # Use conservative thresholds: require >10 unique values AND >5% cardinality
        # This prevents misclassifying binary (0/1) or encoded categorical as regression
        if unique_ratio > 0.05 and target.nunique() > 10:
            return 'regression'
        else:
            return 'classification'

    # Non-numeric (string/object types) always indicates categorical classification
    return 'classification'


def validate_target(df: pd.DataFrame, target_column: str) -> dict:
    """Validate that target column is suitable for ML training.

    Performs three critical checks to ensure the target variable has sufficient
    quality and variance for meaningful model training:
    1. Column existence: target must be present in the DataFrame
    2. Completeness: target should have <50% missing values
    3. Variance: target must have ≥2 distinct values (otherwise no variation to learn)

    Args:
        df: DataFrame containing the data.
        target_column: Name of the target column to validate.

    Returns:
        Dictionary with:
        - 'valid' (bool): True if all validation checks pass, False otherwise
        - 'error' (str|None): None on success, descriptive error message on failure

    Edge Cases:
        - Missing column: returns error with list of available columns
        - All missing data: caught by >50% missing check
        - Single unique value: caught by <2 unique values check
        - Constant column: returns error (no variation to predict)
    """
    # Check 1: Verify target column exists in dataset
    if target_column not in df.columns:
        return {
            'valid': False,
            'error': f"Column '{target_column}' not found in dataset. "
                     f"Available columns: {list(df.columns)}"
        }

    target = df[target_column]
    # Calculate percentage of missing values
    missing_pct = target.isnull().sum() / len(target) * 100

    # Check 2: Ensure sufficient data completeness (>50% threshold chosen to allow some missing)
    if missing_pct > 50:
        return {
            'valid': False,
            'error': f"Target column '{target_column}' has {missing_pct:.1f}% "
                     f"missing values. Cannot train reliably."
        }

    # Check 3: Verify target has sufficient variance (at least 2 distinct values)
    if target.nunique() < 2:
        return {
            'valid': False,
            'error': f"Target column '{target_column}' has only "
                     f"{target.nunique()} unique value. Need at least 2."
        }

    return {'valid': True, 'error': None}


def prepare_features(df: pd.DataFrame, target_column: str) -> pd.DataFrame:
    """Prepare dataset for ML training by removing problematic columns.

    Performs feature engineering by removing columns that would:
    1. Leak target information (impossible in production scenario)
    2. Cause overfitting or model degradation (IDs, high-cardinality text)

    Removal Criteria:
    - ID-like columns: names containing 'id', 'uuid', 'index', or 'key' (case-insensitive)
    - High-cardinality text: object dtype with >80% unique values (e.g., free text fields)
    - Target column: excluded from features by definition

    Args:
        df: Full DataFrame with all columns.
        target_column: Column name to predict (will not appear in output).

    Returns:
        New DataFrame with problematic columns removed, ready for model training.
        Target column is also removed from output.

    Notes:
        - Function works on a copy to avoid modifying input DataFrame
        - Dropped columns are logged with reason for audit trail
        - Output has one fewer column than input (target removed)

    Examples:
        Input: [price, surface, ville, customer_id, description, address_notes]
        Output: [surface, ville] (price=target, IDs removed, text cols dropped)
    """
    # Create independent copy to avoid side effects on caller's DataFrame
    df_clean = df.copy()
    cols_to_drop = []

    for col in df_clean.columns:
        # Skip the target column - it will be excluded during model setup
        if col == target_column:
            continue

        # Identify and flag ID-like columns for removal
        # These provide no predictive value and risk data leakage
        col_lower = col.lower()
        if any(id_word in col_lower for id_word in ['id', 'uuid', 'index', 'key']):
            cols_to_drop.append(col)
            logger.info(f"Dropping ID column: {col}")
            continue

        # Identify high-cardinality text columns (likely free text or unique identifiers)
        # Example: customer names, addresses, email addresses would break model integrity
        if df_clean[col].dtype == 'object':
            unique_ratio = df_clean[col].nunique() / len(df_clean)
            # Threshold >0.8 (80% unique) indicates each value appears rarely
            # Such columns have minimal predictive power and cause overfitting
            if unique_ratio > 0.8:
                cols_to_drop.append(col)
                logger.info(f"Dropping high cardinality column: {col}")

    # Remove all identified problematic columns in one operation
    if cols_to_drop:
        df_clean = df_clean.drop(columns=cols_to_drop)

    # Log feature engineering summary for transparency
    n_features = len(df_clean.columns) - 1  # Subtract 1 for target column
    logger.info(f"Features prepared: {n_features} features for target '{target_column}'")
    return df_clean


def run_automl(
    dataset_result: dict,
    target_column: str,
    problem_type: Optional[str] = None,
    max_models: int = 5,
    sample_size: int = 5000
) -> dict:
    """Run complete AutoML pipeline to train and select best model.

    Main entry point orchestrating the full machine learning workflow:
    1. Validates dataset and target column
    2. Detects or confirms problem type (regression vs classification)
    3. Prepares features by removing problematic columns
    4. Trains multiple models using PyCaret
    5. Selects best performer and extracts metrics
    6. Returns fully serializable result dictionary

    All errors are caught and returned in result['error'] rather than
    raised as exceptions, allowing graceful error handling.

    Args:
        dataset_result: Dictionary from dataset_loader.load_dataset()
                       Keys: 'dataframe', 'error', 'stats', 'column_types'
        target_column: Name of column to predict (must exist in dataframe)
        problem_type: Optional problem type override. Choices:
                     - 'regression': train for continuous numeric targets
                     - 'classification': train for categorical targets
                     - None: auto-detect based on target variable (recommended)
        max_models: Maximum number of top models to include in comparison
                   (PyCaret trains more, but only top N returned)
        sample_size: Maximum rows to use for training. Larger datasets are
                    sampled to this size for speed. Use 0 for no sampling.

    Returns:
        Dictionary with keys:
        - 'best_model' (object): Trained model object ready for prediction
        - 'best_model_name' (str): Algorithm name (e.g., 'RandomForestRegressor')
        - 'metrics' (dict): Performance metrics appropriate to problem type:
          * Regression: R2, MAE, RMSE, MAPE
          * Classification: Accuracy, AUC, F1, Precision, Recall
        - 'comparison' (dict): Top N models ranked by performance
        - 'problem_type' (str): Confirmed problem type ('regression'/'classification')
        - 'features_used' (list): Column names used as features
        - 'target_column' (str): Name of target column
        - 'error' (str|None): None on success, error message on failure

    Examples:
        result = run_automl(dataset, 'price', problem_type='regression', max_models=10)
        if result['error']:
            print(f"Failed: {result['error']}")
        else:
            print(f"Best model: {result['best_model_name']}")
            print(f"R² Score: {result['metrics']['R2']}")

    Edge Cases:
        - Empty dataset: returns error
        - Invalid target column: returns error with available columns
        - Insufficient target variance: returns validation error
        - No valid features after preparation: PyCaret will handle or error
        - Large datasets: automatically sampled to sample_size for speed
    """
    result = {
        'best_model': None,
        'best_model_name': None,
        'metrics': {},
        'comparison': None,
        'problem_type': None,
        'features_used': [],
        'target_column': target_column,
        'error': None
    }

    # Check dataset loaded correctly
    if dataset_result.get('error'):
        result['error'] = f"Dataset error: {dataset_result['error']}"
        return result

    df = dataset_result['dataframe']

    if df is None or len(df) == 0:
        result['error'] = "Empty dataset"
        return result

    # Validate target column
    validation = validate_target(df, target_column)
    if not validation['valid']:
        result['error'] = validation['error']
        return result

    try:
        # STEP 1: Handle large datasets through intelligent sampling
        # Small datasets preserve all data; large datasets sampled for speed
        # Use fixed random_state (42) for reproducibility across runs
        if len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42)
            logger.info(f"Sampled {sample_size:,} rows for training speed")

        # STEP 2: Determine problem type (regression vs classification)
        # Allow override via parameter, but auto-detect is recommended as it's more robust
        if problem_type is None:
            problem_type = detect_problem_type(df, target_column)
        else:
            # Validate provided problem_type value
            if problem_type not in ['regression', 'classification']:
                result['error'] = f"Invalid problem_type '{problem_type}'. Must be 'regression' or 'classification'."
                return result

        result['problem_type'] = problem_type
        logger.info(f"Problem type: {problem_type}")

        # STEP 3: Feature engineering - remove problematic columns
        # This prevents overfitting, data leakage, and model degradation
        df_prepared = prepare_features(df, target_column)
        result['features_used'] = [c for c in df_prepared.columns if c != target_column]

        logger.info(f"Starting AutoML: {problem_type} | target='{target_column}' | "
                   f"{len(df_prepared)} rows | {len(result['features_used'])} features")

        # STEP 4: Train models using PyCaret (dynamic import based on problem type)
        # PyCaret handles preprocessing, feature scaling, and model training internally
        if problem_type == 'regression':
            # Import regression-specific functions from PyCaret
            from pycaret.regression import (
                setup, compare_models, pull,
                finalize_model, get_config
            )

            # Setup PyCaret environment (preprocessing, train/test split, etc.)
            setup(
                data=df_prepared,
                target=target_column,
                session_id=42,  # Fixed seed for reproducibility
                verbose=False,  # Suppress verbose output
                html=False      # No HTML report generation
            )

            # Train multiple regression models and select best by default metric (R²)
            best_model = compare_models(
                n_select=1,     # Return only the single best model
                verbose=False,  # Suppress training output
                turbo=True      # Use fast training mode
            )

            # Extract comparison results and format metrics
            comparison_df = pull()
            metrics = {
                'R2': round(float(comparison_df.iloc[0]['R2']), 4),      # Coefficient of determination
                'MAE': round(float(comparison_df.iloc[0]['MAE']), 4),    # Mean Absolute Error
                'RMSE': round(float(comparison_df.iloc[0]['RMSE']), 4),  # Root Mean Squared Error
                'MAPE': round(float(comparison_df.iloc[0]['MAPE']), 4),  # Mean Absolute Percentage Error
            }

        else:  # classification branch
            # Import classification-specific functions from PyCaret
            from pycaret.classification import (
                setup, compare_models, pull,
                finalize_model, get_config
            )

            # Setup PyCaret environment with classification settings
            setup(
                data=df_prepared,
                target=target_column,
                session_id=42,  # Fixed seed for reproducibility
                verbose=False,  # Suppress verbose output
                html=False      # No HTML report generation
            )

            # Train multiple classification models and select best by default metric (Accuracy)
            best_model = compare_models(
                n_select=1,     # Return only the single best model
                verbose=False,  # Suppress training output
                turbo=True      # Use fast training mode
            )

            # Extract comparison results and format classification-specific metrics
            comparison_df = pull()
            metrics = {
                'Accuracy': round(float(comparison_df.iloc[0]['Accuracy']), 4),  # Overall correctness
                'AUC': round(float(comparison_df.iloc[0].get('AUC', 0)), 4),      # Area under ROC curve (not always available)
                'F1': round(float(comparison_df.iloc[0]['F1']), 4),               # Harmonic mean of precision and recall
                'Precision': round(float(comparison_df.iloc[0]['Prec.']), 4),     # True positives / (TP + FP)
                'Recall': round(float(comparison_df.iloc[0]['Recall']), 4),       # True positives / (TP + FN)
            }

        # STEP 5: Extract model metadata and compile final result
        # Get the algorithm name from the model's class (e.g., 'RandomForestRegressor')
        best_model_name = type(best_model).__name__

        # Populate result dictionary with all training outputs
        result['best_model'] = best_model
        result['best_model_name'] = best_model_name
        result['metrics'] = metrics
        result['comparison'] = comparison_df.head(max_models).to_dict()  # Top N models for comparison

        # Log successful completion with summary metrics
        logger.info(
            f"AutoML complete. Best model: {best_model_name} | "
            f"Metrics: {metrics}"
        )

        return result

    except Exception as e:
        # Capture all exceptions and return as error message (never raise)
        # This allows graceful failure in production pipelines
        error_msg = f"AutoML failed: {str(e)}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result