"""Anomaly detection engine using PyOD + IsolationForest ensemble.

Uses PyOD (Python Outlier Detection) as primary framework
combined with statistical IQR scoring for robust detection.

PyOD algorithms used:
- IForest: isolation-based (handles high dimensional data)
- HBOS: histogram-based (fast, unsupervised)
- KNN: distance-based (finds local outliers)

Use cases: fraud detection, quality control, audit automation.
"""
import logging
import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from pyod.models.iforest import IForest
from pyod.models.hbos import HBOS
from pyod.models.knn import KNN

logger = logging.getLogger(__name__)

# Anomaly score thresholds
SEVERITY_HIGH   = 0.7
SEVERITY_MEDIUM = 0.4
SEVERITY_LOW    = 0.0


def prepare_numeric_matrix(df: pd.DataFrame) -> tuple:
    """Convert DataFrame to numeric matrix for anomaly detection.

    Transforms mixed-type data into a standardized numeric matrix suitable
    for PyOD algorithms. Handles categorical encoding and feature scaling.

    Process:
    1. Encode categorical/object columns using OrdinalEncoder
    2. Select only numeric columns
    3. Impute missing values with column median
    4. Apply StandardScaler normalization (mean=0, std=1)

    Args:
        df: Input DataFrame with mixed types (numeric, categorical, etc.)

    Returns:
        Tuple of:
        - Scaled numpy array (n_samples, n_features) ready for PyOD
        - List of numeric feature names used (order matches array columns)
    """
    df_work = df.copy()

    # Step 1: Encode categorical columns (text/category types)
    # OrdinalEncoder maps categories to integers; unknown values get -1
    cat_cols = df_work.select_dtypes(
        include=['object', 'category']
    ).columns.tolist()

    if cat_cols:
        encoder = OrdinalEncoder(
            handle_unknown='use_encoded_value',
            unknown_value=-1  # Handle unseen categories in inference
        )
        df_work[cat_cols] = encoder.fit_transform(df_work[cat_cols])
        logger.info(f"✓ Encoded {len(cat_cols)} categorical features: {cat_cols}")

    # Step 2: Extract only numeric columns for anomaly detection
    # PyOD algorithms require numeric input; non-numeric filtered out
    numeric_cols = df_work.select_dtypes(
        include=[np.number]
    ).columns.tolist()

    if not numeric_cols:
        logger.warning("⚠ No numeric columns found in dataset")
        return np.array([]), []

    df_numeric = df_work[numeric_cols].copy()

    # Step 3: Impute missing values with column median
    # Median is robust to outliers; PyOD requires complete numeric data
    for col in df_numeric.columns:
        nan_count = df_numeric[col].isna().sum()
        if nan_count > 0:
            median_val = df_numeric[col].median()
            df_numeric[col] = df_numeric[col].fillna(median_val)
            logger.debug(f"  Imputed {nan_count} missing values in '{col}' with median={median_val}")

    # Step 4: Standardize features (zero mean, unit variance)
    # StandardScaler normalization ensures all features contribute equally
    # to PyOD ensemble without scale-dependent bias
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_numeric)

    logger.info(f"✓ Prepared {len(numeric_cols)} features for anomaly detection")
    return X_scaled, numeric_cols


def compute_statistical_scores(df: pd.DataFrame,
                                features_used: list) -> np.ndarray:
    """Compute statistical anomaly scores using IQR (Interquartile Range) method.

    Detects anomalies by measuring deviation from quartile-based statistics.
    For each feature, calculates how many standard IQR distances a value
    is from the median. Scores are aggregated across all features.

    Why IQR?
    - Robust to extreme outliers (uses medians, not means)
    - Interpretable: ~1.5 IQR beyond Q1/Q3 is statistical outlier
    - Complements PyOD ensemble for statistical validation

    Args:
        df: Original DataFrame (unscaled data for quantile computation)
        features_used: List of numeric feature names to analyze

    Returns:
        Numpy array of normalized anomaly scores [0, 1] per row.
        Higher score = more anomalous (further from normal distribution)
    """
    numeric_df = df[features_used].select_dtypes(include=[np.number])

    if numeric_df.empty:
        logger.debug("No numeric features found for statistical scoring")
        return np.zeros(len(df))

    scores = np.zeros(len(numeric_df))

    # Compute IQR-based anomaly score for each feature
    for col in numeric_df.columns:
        values = numeric_df[col].fillna(numeric_df[col].median())
        
        # Calculate quartiles and interquartile range
        q1 = values.quantile(0.25)  # 25th percentile
        q3 = values.quantile(0.75)  # 75th percentile
        iqr = q3 - q1              # Spread of middle 50% of data

        if iqr > 0:
            # Measure normalized distance from median
            median = values.median()
            iqr_distance = np.abs(values - median) / iqr
            
            # Sigmoid-like function maps IQR distance to anomaly score
            # Formula produces: 0 at distance=0, ~0.5 at distance=3*IQR
            col_score = 1 - 1 / (1 + iqr_distance / 3)
            scores += col_score.values

    # Normalize across all features to [0, 1] range
    if scores.max() > 0:
        scores = scores / scores.max()

    logger.debug(f"Statistical IQR scoring complete: mean={scores.mean():.3f}, max={scores.max():.3f}")
    return scores


def run_pyod_ensemble(X_scaled: np.ndarray,
                      contamination: float,
                      random_state: int) -> tuple:
    """Run PyOD ensemble of three complementary anomaly detection algorithms.

    Combines three diverse PyOD models for robust detection:
    - IForest (isolation forest): Fast, handles high-dimensional data
    - HBOS (histogram-based): Assumes feature independence
    - KNN (k-nearest neighbors): Detects local density anomalies

    Ensemble strategy: Vote by averaging normalized decision scores from all
    models, then classify top contamination% as anomalies based on threshold.

    Args:
        X_scaled: Scaled numeric matrix (n_samples, n_features)
        contamination: Expected proportion of anomalies [0.01-0.5]
        random_state: Random seed for reproducibility (IForest/KNN)

    Returns:
        Tuple of:
        - Binary labels array: 1=anomaly, 0=normal (based on percentile threshold)
        - Normalized scores array [0, 1]: higher score = more anomalous
    """
    # Initialize three complementary PyOD models with hyperparameters
    models = {
        'IForest': IForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100  # Ensemble size for isolation trees
        ),
        'HBOS': HBOS(
            contamination=contamination,
            n_bins=10  # Histogram bins for feature distributions
        ),
        'KNN': KNN(
            contamination=contamination,
            n_neighbors=min(5, len(X_scaled) - 1)  # Limit to dataset size
        )
    }

    all_scores = []  # Collect normalized scores from each model

    # Fit each model and extract normalized decision scores
    for name, model in models.items():
        try:
            model.fit(X_scaled)
            
            # Extract raw anomaly scores (PyOD convention: higher = more anomalous)
            raw_scores = model.decision_scores_
            
            # Min-max normalize to [0, 1] for fair ensemble averaging
            score_min = raw_scores.min()
            score_max = raw_scores.max()
            if score_max > score_min:
                # Linear scaling to [0, 1]
                normalized = (raw_scores - score_min) / (score_max - score_min)
            else:
                # All scores identical (rare edge case)
                normalized = np.zeros_like(raw_scores)
            
            all_scores.append(normalized)
            logger.info(f"✓ PyOD {name}: fitted successfully ({len(X_scaled)} samples, {X_scaled.shape[1]} features)")
        except Exception as e:
            logger.warning(f"✗ PyOD {name} failed: {e}. Skipping this model.")

    if not all_scores:
        raise ValueError("✗ All PyOD models failed during fitting. Check data quality.")

    # Ensemble strategy: Average normalized scores from all successful models
    # This democratic voting reduces false positives from individual model bias
    ensemble_scores = np.mean(all_scores, axis=0)

    # Binary classification: Flag top contamination% by score percentile
    # Example: contamination=0.05 → threshold = 95th percentile of scores
    threshold = np.percentile(ensemble_scores, (1 - contamination) * 100)
    labels = (ensemble_scores >= threshold).astype(int)
    
    logger.debug(f"Ensemble scores: threshold={threshold:.4f}, mean={ensemble_scores.mean():.4f}, std={ensemble_scores.std():.4f}")

    return labels, ensemble_scores


def classify_severity(score: float) -> str:
    """Classify anomaly severity based on normalized score.

    Thresholds:
    - HIGH: score ≥ 0.70 (extreme anomalies, requires immediate investigation)
    - MEDIUM: 0.40 ≤ score < 0.70 (moderately anomalous, flag for review)
    - LOW: score < 0.40 (mild deviations, may be normal variation)

    Args:
        score: Normalized anomaly score [0, 1] where 1 = most anomalous

    Returns:
        Severity label: 'high', 'medium', or 'low'
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
    """Run anomaly detection using PyOD ensemble + statistical scoring.

    Main entry point. Uses PyOD (IForest + HBOS + KNN) as primary
    detector combined with IQR statistical scoring for robustness.

    Args:
        dataset_result: Output from dataset_loader.load_dataset()
        contamination: Expected fraction of anomalies (0.01 to 0.5)
        n_top_anomalies: Number of top anomalies to return in detail
        random_state: Seed for reproducibility

    Returns:
        Dictionary with:
        - 'anomaly_count': total anomalies detected
        - 'anomaly_rate': percentage of dataset flagged
        - 'top_anomalies': detailed info on worst anomalies
        - 'anomaly_scores': score for every row
        - 'features_used': features used for detection
        - 'models_used': PyOD models in ensemble
        - 'severity_counts': breakdown by severity
        - 'error': None on success, message on failure
    """
    result = {
        'anomaly_count': 0,
        'anomaly_rate': 0.0,
        'top_anomalies': [],
        'anomaly_scores': [],
        'features_used': [],
        'models_used': ['IForest', 'HBOS', 'KNN'],
        'severity_counts': {'high': 0, 'medium': 0, 'low': 0},
        'error': None
    }

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
            f"━━ Starting anomaly detection ━━\n"
            f"  Dataset: {len(df)} rows × {len(df.columns)} columns\n"
            f"  Contamination: {contamination*100:.1f}% (expect ~{int(len(df)*contamination)} anomalies)\n"
            f"  Expected top-N results: {n_top_anomalies}"
        )

        # Phase 1: Prepare numeric matrix (encoding + scaling)
        X_scaled, features_used = prepare_numeric_matrix(df)

        if len(features_used) == 0:
            result['error'] = "No numeric features found in dataset"
            logger.error(result['error'])
            return result

        result['features_used'] = features_used
        logger.info(f"  Phase 1: Matrix prepared with {len(features_used)} numeric features")

        # Phase 2: Run PyOD ensemble (IForest + HBOS + KNN)
        pyod_labels, pyod_scores = run_pyod_ensemble(
            X_scaled, contamination, random_state
        )
        logger.info(f"  Phase 2: PyOD ensemble completed")

        # Phase 3: Compute statistical IQR scores for robustness
        stat_scores = compute_statistical_scores(df, features_used)
        logger.info(f"  Phase 3: Statistical IQR scoring completed")

        # Phase 4: Hybrid ensemble (PyOD 70% weight + IQR 30% weight)
        # PyOD given higher weight due to proven robustness across datasets
        combined_scores = pyod_scores * 0.7 + stat_scores * 0.3
        result['anomaly_scores'] = combined_scores.tolist()
        logger.debug(f"  Phase 4: Hybrid scores computed (PyOD:70% + IQR:30%)")

        # Identify flagged anomalies from PyOD labels
        anomaly_mask = pyod_labels == 1
        anomaly_count = int(anomaly_mask.sum())
        result['anomaly_count'] = anomaly_count
        result['anomaly_rate'] = round(
            anomaly_count / len(df) * 100, 2
        )

        logger.info(
            f"  Detection Results: Found {anomaly_count} anomalies "
            f"({result['anomaly_rate']}% of {len(df)} rows)"
        )

        # Categorize anomalies by severity for actionable insights
        for is_anomaly, score in zip(anomaly_mask, combined_scores):
            if is_anomaly:
                severity = classify_severity(float(score))
                result['severity_counts'][severity] += 1

        # Extract indices of flagged anomalies for detailed analysis
        anomaly_indices = np.where(anomaly_mask)[0]
        # Rank anomalies by score severity (highest first)
        anomaly_scores_flagged = combined_scores[anomaly_indices]
        top_indices = anomaly_indices[
            np.argsort(anomaly_scores_flagged)[::-1][:n_top_anomalies]
        ]

        # Extract detailed info on worst anomalies for investigation
        logger.info(f"  Analyzing top {min(len(top_indices), n_top_anomalies)} anomalies in detail...")
        
        for rank, idx in enumerate(top_indices, 1):
            row = df.iloc[idx]
            score = float(combined_scores[idx])
            severity = classify_severity(score)

            # Identify which features are driving the anomaly (extreme percentile)
            # Flag features where value is in top/bottom 5% of distribution
            anomalous_features = []
            for col in features_used:
                val = df[col].iloc[idx]
                if pd.notna(val):
                    # Calculate percentile rank (0-100) of this value
                    col_vals = df[col].dropna()
                    percentile = (col_vals < val).mean() * 100
                    
                    # Flag if in extreme tail (top 5% or bottom 5%)
                    if percentile > 95 or percentile < 5:
                        anomalous_features.append({
                            'feature': col,
                            'value': round(float(val), 4) if isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('.','',1).lstrip('-').isdigit()) else str(val),
                            'percentile': round(percentile, 1)  # Percentile rank in dataset
                        })

            result['top_anomalies'].append({
                'row_index': int(idx),
                'anomaly_score': round(score, 4),
                'severity': severity,
                'anomalous_features': anomalous_features,  # Features driving the flag
                'row_data': row.to_dict()
            })

        # Summary statistics
        logger.info(
            f"\n  ─ Severity Breakdown ─\n"
            f"  🔴 High:   {result['severity_counts']['high']} anomalies\n"
            f"  🟡 Medium: {result['severity_counts']['medium']} anomalies\n"
            f"  🟢 Low:    {result['severity_counts']['low']} anomalies\n"
            f"  ✓ Analysis complete"
        )

        return result

    except Exception as e:
        error_msg = f"✗ Anomaly detection failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        result['error'] = error_msg
        return result