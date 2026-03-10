"""Exploratory Data Analysis (EDA) engine for comprehensive dataset profiling.

Automatically generates statistical summaries, distribution analysis, correlation
detection, and outlier identification for any loaded dataset. Provides structured
results suitable for report generation, visualization, and LLM interpretation.

This module works directly with dataset_loader.load_dataset() output and produces
analysis results organized by column type (numeric, categorical) with human-readable
insights highlighting key patterns and anomalies.

Typical usage:
    from backend.engines.analysis.dataset_loader import load_dataset
    from backend.engines.analysis.eda_engine import run_eda

    dataset = load_dataset('data/sample.csv')
    analysis = run_eda(dataset)
    for insight in analysis['insights']:
        print(insight)
"""
import logging
import pandas as pd
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


def analyze_numeric_columns(df: pd.DataFrame, numeric_cols: list) -> dict:
    """Generate comprehensive statistical profile for all numeric columns.

    Computes descriptive statistics (mean, median, std, quartiles), distribution
    shape metrics (skewness with interpretive labels), and identifies potential
    outliers using the 1.5×IQR (Interquartile Range) method. Handles missing
    values by excluding them from calculations and tracking their count.

    Args:
        df: DataFrame containing the data.
        numeric_cols: List of column names identified as numeric types.

    Returns:
        Dictionary mapping column names to their statistical profiles containing:
        - 'mean', 'median', 'std': Central tendency and dispersion measures
        - 'min', 'max', 'q1', 'q3', 'iqr': Range and quartile information
        - 'skewness', 'skew_label': Distribution symmetry (symmetric/right/left-skewed)
        - 'outlier_count', 'outlier_percentage': Anomaly quantification
        - 'missing_count': Number of null/NaN values in the column
    """
    results = {}

    for col in numeric_cols:
        # Remove null/NaN values for statistical calculations
        series = df[col].dropna()

        # Skip columns with no valid data after removing nulls
        if len(series) == 0:
            continue

        # Calculate quartiles and identify outliers using 1.5×IQR method (standard in statistics)
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        outlier_count = int(((series < (q1 - 1.5 * iqr)) | (series > (q3 + 1.5 * iqr))).sum())

        # Assess distribution symmetry using skewness coefficient
        # Values near 0 indicate symmetric distribution; positive/negative indicate right/left skew
        skewness = float(series.skew())
        if abs(skewness) < 0.5:
            skew_label = 'symmetric'
        elif skewness > 0:
            skew_label = 'right-skewed'
        else:
            skew_label = 'left-skewed'

        results[col] = {
            'mean': round(float(series.mean()), 4),
            'median': round(float(series.median()), 4),
            'std': round(float(series.std()), 4),
            'min': round(float(series.min()), 4),
            'max': round(float(series.max()), 4),
            'q1': round(float(q1), 4),
            'q3': round(float(q3), 4),
            'iqr': round(float(iqr), 4),
            'skewness': round(skewness, 4),
            'skew_label': skew_label,
            'outlier_count': outlier_count,
            'outlier_percentage': round(outlier_count / len(series) * 100, 2),
            'missing_count': int(df[col].isnull().sum())
        }

    logger.info(f"Analyzed {len(results)} numeric columns")
    print(f"[eda_engine] ✓ Numeric analysis: {len(results)} columns profiled")
    return results


def analyze_categorical_columns(df: pd.DataFrame, categorical_cols: list) -> dict:
    """Generate comprehensive frequency and distribution profiles for categorical columns.

    Analyzes the distribution of values in each categorical column, identifying
    the most common value, value distribution dominance, and diversity metrics.
    Top 10 values are extracted for both frequency analysis and cardinality assessment.

    Args:
        df: DataFrame containing the data.
        categorical_cols: List of column names identified as categorical types.

    Returns:
        Dictionary mapping column names to their frequency profiles containing:
        - 'unique_count': Total number of distinct values
        - 'most_common': Most frequently occurring value
        - 'most_common_count': Absolute frequency of most common value
        - 'most_common_percentage': Percentage of data dominated by most common value
        - 'top_10_values': Dictionary of 10 most frequent values with their counts
        - 'missing_count': Number of null/NaN values in the column
    """
    results = {}

    for col in categorical_cols:
        # Remove null/NaN values for frequency analysis
        series = df[col].dropna()

        # Skip columns with no valid data after removing nulls
        if len(series) == 0:
            continue

        # Count occurrences of each unique value, sorted by frequency descending
        value_counts = series.value_counts()
        # Extract top 10 most common values for summary reporting
        top_10 = value_counts.head(10)

        results[col] = {
            'unique_count': int(series.nunique()),
            'most_common': str(value_counts.index[0]),
            'most_common_count': int(value_counts.iloc[0]),
            'most_common_percentage': round(value_counts.iloc[0] / len(series) * 100, 2),
            'top_10_values': top_10.to_dict(),
            'missing_count': int(df[col].isnull().sum())
        }

    logger.info(f"Analyzed {len(results)} categorical columns")
    print(f"[eda_engine] ✓ Categorical analysis: {len(results)} columns profiled")
    return results


def analyze_correlations(df: pd.DataFrame, numeric_cols: list) -> dict:
    """Compute pairwise Pearson correlations between all numeric columns.

    Generates a complete correlation matrix and identifies strong linear relationships
    (|r| > 0.7) indicating potential multicollinearity, causality, or data artifacts.
    Classifies relationship strength as 'very strong' (|r| > 0.9) or 'strong' (|r| > 0.7),
    and direction as positive or negative.

    Args:
        df: DataFrame containing the data.
        numeric_cols: List of numeric column names to correlate.

    Returns:
        Dictionary containing:
        - 'matrix': Full Pearson correlation matrix as nested dictionary
        - 'strong_pairs': List of significant correlation pairs with details:
          * 'column_a', 'column_b': Column names being correlated
          * 'correlation': Pearson correlation coefficient (rounded to 4 decimals)
          * 'strength': Categorical strength assessment (very strong/strong)
          * 'direction': Relationship sign (positive/negative)
    """
    # Correlation requires at least 2 numeric columns
    if len(numeric_cols) < 2:
        logger.info("Skipping correlation analysis: fewer than 2 numeric columns")
        return {'matrix': {}, 'strong_pairs': []}

    # Compute pairwise Pearson correlation coefficients between all numeric columns
    corr_matrix = df[numeric_cols].corr(method='pearson').round(4)

    # Identify and classify significant correlations for insight generation
    strong_pairs = []
    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            col_a = numeric_cols[i]
            col_b = numeric_cols[j]
            corr_value = corr_matrix.loc[col_a, col_b]

            # Flag correlations with |r| > 0.7 as statistically significant relationships
            if abs(corr_value) > 0.7:
                strong_pairs.append({
                    'column_a': col_a,
                    'column_b': col_b,
                    'correlation': round(float(corr_value), 4),
                    'strength': 'very strong' if abs(corr_value) > 0.9 else 'strong',
                    'direction': 'positive' if corr_value > 0 else 'negative'
                })

    logger.info(f"Found {len(strong_pairs)} strong correlations")
    print(f"[eda_engine] ✓ Correlation analysis: {len(strong_pairs)} significant pairs detected")
    return {
        'matrix': corr_matrix.to_dict(),
        'strong_pairs': strong_pairs
    }


def generate_insights(
    numeric_analysis: dict,
    categorical_analysis: dict,
    correlation_analysis: dict,
    stats: dict
) -> list:
    """Generate human-readable insights synthesized from all analysis components.

    Produces a prioritized list of key findings highlighting data quality issues,
    distribution anomalies, relationships, and patterns. Insights are suitable
    for LLM consumption, report generation, and stakeholder communication.

    Generated insights cover:
    - Dataset dimensions and completeness
    - Missing data and duplicate row detection
    - Distribution anomalies (outliers, skewness) in numeric columns
    - Value dominance and diversity in categorical columns
    - Significant correlations between numeric columns

    Args:
        numeric_analysis: Statistical profiles from analyze_numeric_columns().
        categorical_analysis: Frequency profiles from analyze_categorical_columns().
        correlation_analysis: Correlation matrix from analyze_correlations().
        stats: Basic metadata from dataset_loader.get_basic_stats().

    Returns:
        List of insight strings ordered by importance (dataset overview first,
        then quality issues, then column-specific patterns, then correlations).
    """
    insights = []

    # Dataset overview: dimension and structure
    insights.append(
        f"Dataset contains {stats['rows']:,} rows and {stats['columns']} columns."
    )

    # Data quality check: missing values indicate data collection or preprocessing issues
    total_missing = sum(stats['missing_values'].values())
    if total_missing > 0:
        worst_col = max(stats['missing_percentage'], key=stats['missing_percentage'].get)
        insights.append(
            f"Missing values detected: {total_missing:,} total. "
            f"Worst column: '{worst_col}' with {stats['missing_percentage'][worst_col]}% missing."
        )
    else:
        insights.append("No missing values detected. Dataset is complete.")

    # Data quality check: duplicate rows suggest data entry errors or merge artifacts
    if stats['duplicate_rows'] > 0:
        insights.append(
            f"Found {stats['duplicate_rows']:,} duplicate rows "
            f"({round(stats['duplicate_rows']/stats['rows']*100, 1)}% of data)."
        )

    # Numeric column insights: highlight statistical anomalies and distribution patterns
    for col, profile in numeric_analysis.items():
        # Flag columns with significant outlier presence (>5% suggests data quality issue or legitimate high-variance)
        if profile['outlier_percentage'] > 5:
            insights.append(
                f"Column '{col}' has {profile['outlier_percentage']}% outliers. "
                f"Range: {profile['min']} to {profile['max']}. "
                f"Distribution is {profile['skew_label']}."
            )
        # Non-symmetric distributions suggest transformation may be needed for some analyses
        if profile['skew_label'] != 'symmetric':
            insights.append(
                f"Column '{col}' is {profile['skew_label']} "
                f"(skewness={profile['skewness']}). "
                f"Median ({profile['median']}) differs from mean ({profile['mean']})."
            )

    # Categorical column insights: identify dominance patterns and cardinality issues
    for col, profile in categorical_analysis.items():
        # High dominance (>50%) suggests limited information content or imbalanced categories
        if profile['most_common_percentage'] > 50:
            insights.append(
                f"Column '{col}' is dominated by '{profile['most_common']}' "
                f"({profile['most_common_percentage']}% of values). "
                f"Only {profile['unique_count']} unique values total."
            )

    # Correlation insights: indicate potential multicollinearity, confounding, or causality
    for pair in correlation_analysis.get('strong_pairs', []):
        insights.append(
            f"Strong {pair['direction']} correlation ({pair['correlation']}) "
            f"between '{pair['column_a']}' and '{pair['column_b']}'."
        )

    logger.info(f"Generated {len(insights)} insights")
    print(f"[eda_engine] ✓ Insight generation: {len(insights)} findings extracted")
    return insights


def run_eda(dataset_result: dict) -> dict:
    """Run complete exploratory data analysis (EDA) on a loaded dataset.

    Main entry point orchestrating all analysis functions. Takes the output of
    dataset_loader.load_dataset(), runs numeric/categorical/correlation analyses,
    synthesizes insights, and returns comprehensive results ready for visualization,
    report generation, or downstream machine learning tasks.

    Error handling ensures that data loading failures are captured and reported
    without raising exceptions, allowing graceful degradation in pipelines.

    Args:
        dataset_result: Dictionary returned by dataset_loader.load_dataset()
                       containing 'dataframe', 'column_types', 'stats', 'error'.

    Returns:
        Dictionary containing:
        - 'numeric' (dict): Statistical profiles for all numeric columns
        - 'categorical' (dict): Frequency/value profiles for categorical columns
        - 'correlations' (dict): Pearson correlation matrix and significant pairs
        - 'insights' (list): Prioritized human-readable findings and patterns
        - 'error' (str|None): None on success, descriptive error message on failure
    """
    result = {
        'numeric': {},
        'categorical': {},
        'correlations': {},
        'insights': [],
        'error': None
    }

    # Validate that dataset loading succeeded before attempting analysis
    if dataset_result.get('error'):
        result['error'] = f"Cannot run EDA: dataset failed to load: {dataset_result['error']}"
        logger.error(result['error'])
        return result

    # Extract analysis components from dataset result
    df = dataset_result['dataframe']
    col_types = dataset_result['column_types']
    stats = dataset_result['stats']

    # Verify dataframe is populated and non-empty
    if df is None or len(df) == 0:
        result['error'] = "Cannot run EDA: dataframe is empty"
        logger.error(result['error'])
        return result

    try:
        logger.info(f"Starting EDA on {stats['rows']:,} rows, {stats['columns']} columns")
        print(f"\n[eda_engine] ═══════════════════════════════════════════")
        print(f"[eda_engine] Starting Exploratory Data Analysis")
        print(f"[eda_engine] Dataset: {stats['rows']:,} rows × {stats['columns']} columns")
        print(f"[eda_engine] ───────────────────────────────────────────")

        result['numeric'] = analyze_numeric_columns(df, col_types.get('numeric', []))
        result['categorical'] = analyze_categorical_columns(df, col_types.get('categorical', []))
        result['correlations'] = analyze_correlations(df, col_types.get('numeric', []))
        result['insights'] = generate_insights(
            result['numeric'],
            result['categorical'],
            result['correlations'],
            stats
        )

        logger.info(f"EDA complete. Generated {len(result['insights'])} insights.")
        print(f"[eda_engine] ───────────────────────────────────────────")
        print(f"[eda_engine] ✓ EDA complete: {len(result['insights'])} insights generated")
        print(f"[eda_engine] ═══════════════════════════════════════════\n")
        return result

    except Exception as e:
        error_msg = f"EDA failed: {str(e)}"
        logger.error(error_msg)
        print(f"[eda_engine] ✗ ERROR: {error_msg}")
        result['error'] = error_msg
        return result