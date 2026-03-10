"""Anomaly detection engine using ensemble algorithms for unsupervised outlier detection.

Detects outliers and anomalous patterns in datasets without requiring a target column.
Uses ensemble approach combining two complementary algorithms:
1. IsolationForest: Isolation-based detection (70% weight)
2. Statistical IQR: Distance-based detection (30% weight)

ARCHITECTURE:
- IsolationForest: Random isolation trees; anomalies isolated in fewer splits
  └─ Strengths: High-dimensional efficiency, non-linear patterns
  └─ Returns: Binary labels (-1=anomaly, 1=normal) + decision scores
- Statistical IQR: Interquartile Range per feature, robust and interpretable
  └─ Strengths: Explains which features are anomalous
  └─ Returns: Continuous scores (0-1) for anomaly severity
- Ensemble: 70% IsolationForest + 30% Statistical for robust detection

SEVERITY LEVELS:
- HIGH (≥0.7): Most anomalous, requires investigation
- MEDIUM (0.4-0.7): Moderately unusual
- LOW (<0.4): Mildly anomalous

USE CASES: Fraud detection, quality control, data audit automation

COMPLIANCE: EU AI Act, GDPR, French RGPD transparency requirements
"""
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

# SEVERITY THRESHOLDS: Classify anomalies by how extreme they are
# These thresholds are applied to the combined ensemble score (0-1 range)
SEVERITY_HIGH   = 0.7   # Score ≥ 0.7: Most anomalous (top 5-10% of anomalies)
SEVERITY_MEDIUM = 0.4   # Score 0.4-0.7: Moderately anomalous (middle 30-50%)
SEVERITY_LOW    = 0.0   # Score < 0.4: Mildly anomalous (normal variation boundary)


def prepare_numeric_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Convert DataFrame to numeric matrix for anomaly detection algorithms.

    Anomaly detection requires numeric input. Handles mixed-type data:
    1. Encode: Categorical → integers (0, 1, 2, ...)
    2. Extract: Keep only numeric columns
    3. Impute: Fill missing with column medians (robust to outliers)
    4. Scale: Normalize to mean=0, std=1 for fair distance comparison
    5. Return: Scaled matrix ready for IsolationForest

    Feature scaling is critical: Without it, large-range features (salary €0-100k)
    dominate small-range features (rating 1-5). StandardScaler ensures each
    feature contributes equally to anomaly detection.

    Args:
        df: Input DataFrame with potentially mixed types and missing values.

    Returns:
        Tuple of (df_scaled, features_used):
        - df_scaled: Numeric DataFrame with scaled features
        - features_used: List of feature names in order
    """
    df_work = df.copy()
    features_used = []

    # STEP 1: Encode categorical columns to numeric (required by algorithms)
    # OrdinalEncoder: converts 'Paris', 'Lyon', 'Marseille' → 0, 1, 2
    cat_cols = df_work.select_dtypes(
        include=['object', 'category']
    ).columns.tolist()

    if cat_cols:
        encoder = OrdinalEncoder(
            handle_unknown='use_encoded_value',
            unknown_value=-1  # Unseen categories → -1 (distinct anomaly signal)
        )
        df_work[cat_cols] = encoder.fit_transform(df_work[cat_cols])
        logger.info(f"Encoded {len(cat_cols)} categorical features")

    # STEP 2: Extract numeric columns (anomaly algorithms need numbers)
    numeric_cols = df_work.select_dtypes(include=[np.number]).columns.tolist()

    if not numeric_cols:
        logger.warning("No numeric features found after encoding")
        return pd.DataFrame(), []

    df_numeric = df_work[numeric_cols].copy()

    # STEP 3: Handle missing values with median (robust to outliers)
    for col in df_numeric.columns:
        missing_count = df_numeric[col].isna().sum()
        if missing_count > 0:
            median_val = df_numeric[col].median()
            df_numeric[col] = df_numeric[col].fillna(median_val)
            logger.info(f"Filled {missing_count} missing in {col}")

    # STEP 4: Normalize features to equal scale (mean=0, std=1)
    # Without scaling: €100k salary dominates 1-5 rating
    scaler = StandardScaler()
    df_scaled = pd.DataFrame(
        scaler.fit_transform(df_numeric),
        columns=numeric_cols
    )

    features_used = numeric_cols
    logger.info(f"Prepared {len(features_used)} numeric features for anomaly detection")

    return df_scaled, features_used


def compute_statistical_scores(df_original: pd.DataFrame,
                                features_used: list) -> np.ndarray:
    """Compute statistical anomaly scores using Interquartile Range (IQR) method.

    Measures how anomalous each data point is based on distance from IQR bounds.
    IQR = Q3 - Q1 where Q1=25th percentile, Q3=75th percentile, Q2=median.

    INTERPRETATION:
    - Values within ±1.5×IQR of median: Normal (5th to 95th percentile roughly)
    - Values beyond ±3×IQR: Extremely anomalous (statistical outlier)
    - Score formula: How many IQRs away from median, converted to 0-1 range

    WHY IQR?
    - Resistant to extreme outliers (unlike mean/std which can be skewed)
    - Interpretable (directly tells: "Value is 5 IQRs above median")
    - Complements IsolationForest (statistical vs isolation perspective)

    Args:
        df_original: Original DataFrame before scaling (for interpretable units).
        features_used: List of numeric feature names to analyze.

    Returns:
        Array of statistical anomaly scores (0.0 to 1.0) with one score per row.
        Higher score = more anomalous based on statistical criteria.
    """
    numeric_df = df_original[features_used].select_dtypes(
        include=[np.number]
    )

    if numeric_df.empty:
        return np.zeros(len(df_original))

    scores = np.zeros(len(numeric_df))

    # Compute IQR-based anomaly score for each feature
    for col in numeric_df.columns:
        values = numeric_df[col].fillna(numeric_df[col].median())
        q1 = values.quantile(0.25)  # 25th percentile
        q3 = values.quantile(0.75)  # 75th percentile
        iqr = q3 - q1  # Interquartile range

        if iqr > 0:
            # Measure distance from median in IQR units
            # Values within ±1.5 IQR = normal, beyond ±3 IQR = extreme
            median = values.median()
            iqr_distance = np.abs(values - median) / iqr
            # Convert IQR distance to 0-1 anomaly score using sigmoid-like function
            # Higher distance = higher score (more anomalous)
            col_score = 1 - 1 / (1 + iqr_distance / 3)
            scores += col_score.values

    # Normalize across all features to 0-1 range
    if scores.max() > 0:
        scores = scores / scores.max()

    return scores


def classify_severity(score: float) -> str:
    """Classify anomaly severity from ensemble score (0-1 range).

    Uses SEVERITY_HIGH and SEVERITY_MEDIUM thresholds to enable prioritization:
    focus investigation on 'high' severity first, then 'medium', then 'low'.

    Args:
        score: Ensemble anomaly score between 0.0 and 1.0.
              Combines IsolationForest (70%) + Statistical (30%).

    Returns:
        Severity classification: 'high' (≥0.7), 'medium' (0.4-0.7), or 'low' (<0.4).
    """
    if score >= SEVERITY_HIGH:
        return 'high'
    elif score >= SEVERITY_MEDIUM:
        return 'medium'
    else:
        return 'low'


def detect_anomalies(
    dataset_result: dict,
    contamination: float = 0.05,
    n_top_anomalies: int = 10,
    random_state: int = 42
) -> dict:
    """Run anomaly detection on a loaded dataset using ensemble algorithms.

    MAIN ENTRY POINT for unsupervised anomaly detection. Combines IsolationForest
    and statistical IQR scoring to identify unusual patterns in data.

    WORKFLOW:
    STEP 1: Validate input dataset (not empty, has minimum rows)
    STEP 2: Prepare numeric matrix (encode categories, scale features)
    STEP 3: Train IsolationForest (detects isolation-based anomalies)
    STEP 4: Compute statistical scores (IQR-based anomaly metrics)
    STEP 5: Combine scores with weighted ensemble (70% IF + 30% Statistical)
    STEP 6: Classify anomalies as HIGH/MEDIUM/LOW severity
    STEP 7: Extract top anomalies with feature-level explanations
    STEP 8: Return complete anomaly report with statistics

    CONTAMINATION PARAMETER:
    Expected fraction of anomalies in dataset (IsolationForest parameter).
    - 0.01: Expect ~1% anomalies (very strict, for clean data)
    - 0.05: Expect ~5% anomalies (default, balanced)
    - 0.10: Expect ~10% anomalies (lenient, for noisy data)
    Should roughly match domain knowledge of anomaly frequency.

    FEATURE IMPORTANCE:
    Top anomalies report which specific features are anomalous:
    - Uses percentile ranking (<5th or >95th percentile = flagged)
    - Helps explain: "This transaction anomalous because amount=€50k > 95th percentile"

    Args:
        dataset_result: Output from dataset_loader.load_dataset() with 'dataframe' key.
        contamination: Expected anomaly fraction (0.01 to 0.5). Default 0.05.
                      Tune based on domain knowledge. Financial fraud 0.01-0.05.
        n_top_anomalies: Number of top anomalies to return detailed analysis for.
                        Default 10. Higher values give more context but slower.
        random_state: Random seed for reproducibility (default 42).

    Returns:
        Dictionary with complete anomaly detection report:
        {
            'anomaly_count': int,  # Number of rows flagged as anomalies
            'anomaly_rate': float,  # Percentage of total rows (0-100)
            'anomaly_scores': list,  # Score for every row (0-1, all rows)
            'features_used': list,  # Feature names used for detection
            'severity_counts': {  # Breakdown by severity
                'high': int,      # Most anomalous (score ≥ 0.7)
                'medium': int,    # Moderately anomalous (0.4-0.7)
                'low': int        # Mildly anomalous (< 0.4)
            },
            'top_anomalies': [  # Detailed info on worst n_top_anomalies
                {
                    'row_index': int,  # Index in original dataset
                    'anomaly_score': float,  # Combined ensemble score
                    'severity': str,  # 'high', 'medium', or 'low'
                    'anomalous_features': [{  # Which features are unusual
                        'feature': str,  # Feature name
                        'value': float,  # Actual value
                        'percentile': float  # Where value ranks (0-100)
                    }],
                    'row_data': dict  # All feature values
                }
            ],
            'error': str or None  # Error if failed, None if successful
        }

    Examples:
        # Standard usage
        >>> dataset = load_dataset('data.csv')
        >>> result = detect_anomalies(dataset, contamination=0.05)
        >>> print(f\"Found {result['anomaly_count']} anomalies\")
        >>> for anom in result['top_anomalies'][:3]:
        >>>     print(anom['anomalous_features'])

    Note:
        - IsolationForest is stochastic; consistent random_state for reproducibility.
        - Contamination is a hint; actual count may vary slightly.
        - Anomaly scores comparable across rows but not across different datasets.
    """
    result = {
        'anomaly_count': 0,
        'anomaly_rate': 0.0,
        'top_anomalies': [],
        'anomaly_scores': [],
        'features_used': [],
        'severity_counts': {'high': 0, 'medium': 0, 'low': 0},
        'error': None
    }

    # STEP 1: Validate input dataset
    if dataset_result.get('error'):
        result['error'] = f"Dataset error: {dataset_result['error']}"
        return result

    df = dataset_result['dataframe']

    if df is None or len(df) == 0:
        result['error'] = "Empty dataset"
        return result

    if len(df) < 10:
        result['error'] = f"Too few rows ({len(df)}). Need at least 10."
        return result

    try:
        logger.info(
            f"Starting anomaly detection: {len(df)} rows, "
            f"{len(df.columns)} columns, contamination={contamination}"
        )

        # STEP 2: Prepare numeric matrix (encode, scale)
        df_scaled, features_used = prepare_numeric_matrix(df)

        if df_scaled.empty or len(features_used) == 0:
            result['error'] = "No numeric features found for anomaly detection"
            return result

        result['features_used'] = features_used

        # STEP 3: IsolationForest detection
        # Isolation-based: anomalies isolated in fewer random splits across features
        iso_forest = IsolationForest(
            contamination=contamination,  # Expected anomaly fraction
            random_state=random_state,  # Seed for reproducibility
            n_estimators=100  # Number of isolation trees
        )
        iso_labels = iso_forest.fit_predict(df_scaled)  # -1=anomaly, 1=normal
        iso_scores = iso_forest.decision_function(df_scaled)  # Raw scores

        # Normalize IsolationForest scores to 0-1
        # Lower decision_function score = more anomalous
        iso_scores_normalized = 1 - (
            (iso_scores - iso_scores.min()) /
            (iso_scores.max() - iso_scores.min() + 1e-10)
        )

        # STEP 4: Statistical scores (IQR-based)
        stat_scores = compute_statistical_scores(df, features_used)

        # STEP 5: Ensemble: combine both scores
        # 70% weight IsolationForest (robust to high dimensions)
        # 30% weight Statistical (interpretable per-feature)
        combined_scores = (iso_scores_normalized * 0.7 + stat_scores * 0.3)

        result['anomaly_scores'] = combined_scores.tolist()

        # STEP 6: Anomalies = rows flagged by IsolationForest
        anomaly_mask = iso_labels == -1
        anomaly_count = int(anomaly_mask.sum())
        result['anomaly_count'] = anomaly_count
        result['anomaly_rate'] = round(
            anomaly_count / len(df) * 100, 2
        )

        logger.info(
            f"Detected {anomaly_count} anomalies "
            f"({result['anomaly_rate']}% of data)"
        )

        # STEP 6b: Classify by severity
        for i, (is_anomaly, score) in enumerate(
            zip(anomaly_mask, combined_scores)
        ):
            if is_anomaly:
                severity = classify_severity(float(score))
                result['severity_counts'][severity] += 1

        # STEP 7: Extract top anomalies with explanations
        anomaly_indices = np.where(anomaly_mask)[0]
        anomaly_scores_for_flagged = combined_scores[anomaly_indices]
        top_indices = anomaly_indices[
            np.argsort(anomaly_scores_for_flagged)[::-1][:n_top_anomalies]
        ]

        for idx in top_indices:
            row = df.iloc[idx]
            score = float(combined_scores[idx])
            severity = classify_severity(score)

            # Find which features are driving this anomaly
            row_numeric = df[features_used].iloc[idx]
            anomalous_features = []
            for col in features_used:
                val = row_numeric[col]
                if pd.notna(val):
                    col_vals = df[col].dropna()
                    # Percentile: where does this value rank? (0-100)
                    percentile = (col_vals < val).mean() * 100
                    # Flag if < 5th or > 95th percentile
                    if percentile > 95 or percentile < 5:
                        anomalous_features.append({
                            'feature': col,
                            'value': round(float(val), 4),
                            'percentile': round(percentile, 1)
                        })

            result['top_anomalies'].append({
                'row_index': int(idx),
                'anomaly_score': round(score, 4),
                'severity': severity,
                'anomalous_features': anomalous_features,
                'row_data': row.to_dict()
            })

        logger.info(
            f"Anomaly detection complete. "
            f"High: {result['severity_counts']['high']} | "
            f"Medium: {result['severity_counts']['medium']} | "
            f"Low: {result['severity_counts']['low']}"
        )

        return result

    except Exception as e:
        error_msg = f"Anomaly detection failed: {str(e)}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result