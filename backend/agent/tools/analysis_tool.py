"""analysis_tool.py — Master Agent analysis tool integrating all Phase 1 engines

Provides unified entry point for CSV dataset analysis through LangGraph agent.

Architecture Overview:
- Single Agent Tool: Called by LangGraph master agent for analysis workflows
- Four-Stage Pipeline: Load → EDA → AutoML+SHAP → Anomaly Detection
- Graceful Degradation: Missing optional components (AutoML, SHAP) don't fail pipeline
- French Output: All narratives generated in French for CNIL compliance
- Error Handling: Captured and returned, never raises exceptions to caller

Phase 1 Engine Integration:
- Dataset Loader: Validates CSV format and loads to pandas DataFrame
- EDA Engine: Statistical insights, distributions, correlations, missing data patterns
- AutoML Pipeline: Automatic feature engineering, model selection, hyperparameter tuning
- SHAP Explainer: Feature importance from trained model (only if target specified)
- Anomaly Detector: Unsupervised detection of outliers and data quality issues

Pipeline Workflow:
1. Validation: Check file exists and is CSV format
2. Load: Parse CSV into DataFrame with type inference
3. Analysis: Run EDA for statistical insights (always)
4. ML: Run AutoML + SHAP only if target_column specified (optional)
5. Quality: Run anomaly detection (always)
6. Synthesis: Build French narrative combining all results
7. Return: Structured dict with success flag and all results

Integration with Master Agent:
- Called from: backend.agent.nodes.execute_analysis()
- Input from state: dataset_path (str), target_column (Optional[str])
- Output to state: result dict with all analysis outputs
- Error handling: Returns success=False with error message (graceful)

Usage by Agent:
    state["task_type"] = "analysis"
    state["dataset_path"] = "data/processed/sales.csv"
    state["target_column"] = "revenue"  # Optional
    result = run_analysis(state["dataset_path"], state["target_column"])
    state["result"] = result

Performance Characteristics:
- Load: 100-500ms (I/O bound on file size)
- EDA: 500-2000ms (statistical computations)
- AutoML: 5-30 seconds (model training, 10+ candidate models tested)
- SHAP: 1-5 seconds (feature importance calculation)
- Anomaly: 1-3 seconds (isolation forest or similar)
- Total typical: 10-40 seconds per dataset

Error Scenarios Handled:
- File not found: Returns graceful error, no exception
- Not a CSV: Validates extension, returns error
- Load failure: DataFrame parsing issues logged, error returned
- EDA failure: Logged as warning, analysis continues without insights
- AutoML failure: Logged as warning, analysis continues without model
- Anomaly failure: Logged as warning, analysis continues
- Empty/corrupted data: Gracefully handled by each engine

Dependencies:
- logging: Standard library for operation tracking
- pathlib: Standard library for file path validation
- backend.engines.analysis: All four Phase 1 analysis engines
"""

import logging
from pathlib import Path
from backend.engines.analysis.dataset_loader import load_dataset
from backend.engines.analysis.eda_engine import run_eda
from backend.engines.analysis.automl_pipeline import run_automl
from backend.engines.analysis.shap_explainer import explain_model
from backend.engines.analysis.anomaly_detector import detect_anomalies

logger = logging.getLogger(__name__)


def run_analysis(dataset_path: str, target_column: str = None) -> dict:
    """Execute complete analysis pipeline on CSV dataset with all Phase 1 engines.

    Four-stage pipeline that progressively analyzes data through domain engines:
    1. Validation & Load: Check file exists, is CSV, parse to DataFrame
    2. EDA: Generate statistical insights (distributions, correlations, missing data)
    3. AutoML + SHAP: Train model (if target provided), generate importance scores
    4. Anomaly Detection: Find outliers and data quality issues
    5. Synthesis: Build French narrative combining all insights

    Args:
        dataset_path (str):
            Path to CSV file for analysis.
            - Type: String (absolute or relative path)
            - Example: "data/processed/sales_2025.csv" or "/data/raw/sensor.csv"
            - Validation: Must exist and have .csv extension
            - Error handling: Returns {success: False, error: "..."} if invalid
            - Performance: File I/O 100-500ms depending on size

        target_column (Optional[str]):
            Column name for supervised ML prediction (AutoML + SHAP).
            - Type: String (column name from DataFrame)
            - Default: None (skips AutoML and SHAP if not provided)
            - Example: "revenue", "churn", "price"
            - Scope: Only used if provided AND exists in DataFrame
            - Effect: Determines if AutoML/SHAP stages execute
            - Notes: Can be numeric (regression) or categorical (classification)
            - Error handling: Gracefully skipped if column not found

    Returns:
        dict: Structured analysis result with following fields:

        success (bool):
            Whether pipeline completed without fatal errors.
            - True: All engines ran (some may have returned empty results)
            - False: File not found, parse failure, or critical error
            - Usage: Check before accessing other fields

        dataset_path (str):
            Original path provided to function (for reference).
            - Value: Same as input parameter
            - Usage: Confirms which file was analyzed

        rows (int):
            Number of data rows in DataFrame.
            - Type: Integer > 0
            - Example: 10000, 50000, 1000000

        columns (int):
            Number of features/columns in DataFrame.
            - Type: Integer > 0
            - Example: 15, 50, 200

        eda_insights (list[str]):
            List of statistical insight strings from EDA engine.
            - Type: List of human-readable strings in French
            - Content: Distributions, correlations, missing patterns, outliers
            - Empty if: EDA engine failed or returned no insights
            - Limit: Typically 3-10 insights per analysis

        best_model (str or None):
            Name of best ML model selected by AutoML (if target provided).
            - Type: String (model name) or None
            - Example: "RandomForest", "XGBoost", "GradientBoosting"
            - None if: No target column OR AutoML failed

        metrics (dict):
            Performance metrics for best_model on test set.
            - Type: Dictionary with metric_name: value pairs
            - Example: {"accuracy": 0.92, "f1": 0.85, "auc": 0.89}
            - Empty if: No target column OR AutoML failed
            - Precision: Values typically 3 decimal places (0.000-1.000)

        top_features (list[dict]):
            Feature importance scores from SHAP explainer (top 5).
            - Type: List of dicts with {"feature": str, "importance": float}
            - Example: [{"feature": "age", "importance": 0.35}, ...]
            - Empty if: No target column OR SHAP failed
            - Count: Max 5 features (most important only)

        anomalies (dict):
            Summary of detected data quality issues.
            - Total entries: {"total": int, "percentage": float}
            - Severity breakdown: {"high": int, "medium": int, "low": int}
            - Example: {"total": 150, "percentage": 1.5, "high": 10, "medium": 40, "low": 100}
            - Empty if: Anomaly detection failed

        answer (str):
            French narrative summary combining all analysis results.
            - Type: Multi-paragraph Markdown-formatted French text
            - Language: 100% French for CNIL compliance and user base
            - Length: Typically 500-1500 characters
            - Content: Synthesizes filename, dimensions, EDA, model, features, anomalies
            - Format: Multiple bullet points with **bold** headings
            - Usage: Display to end user as final analysis report

        error (str or None):
            Error message if pipeline failed (only when success=False).
            - Type: String (human-readable error) or None
            - None if: success=True (no error occurred)
            - Content: Specific error description in French
            - Example: "Fichier non trouvé: data/missing.csv"
            - Logging: Also logged at ERROR level before returning

    Error Scenarios and Recovery:
        - File not found → Returns {"success": False, "error": "Fichier non trouvé: ..."}
        - Wrong extension → Returns {"success": False, "error": "Le fichier doit être un CSV: ..."}
        - Parse failure → Returns {"success": False, "error": "Erreur de chargement: ..."}
        - EDA failure → Continues with empty insights (warning logged)
        - AutoML failure → Continues without model (warning logged)
        - Anomaly failure → Continues with empty anomalies (warning logged)
        - Returns {"success": True, ...} even if some engines failed

    Performance Characteristics:
        - Small dataset (< 10K rows): 5-15 seconds total
        - Medium dataset (10K-100K rows): 10-30 seconds total
        - Large dataset (> 100K rows): 20-60 seconds total
        - Dominated by: AutoML (70-80% of total time when target provided)

    Usage in Agent Context:
        Called from: backend.agent.nodes.execute_analysis(state)
        
        # Agent node execution pattern:
        def execute_analysis(state: AgentState) -> AgentState:
            dataset_path = state["dataset_path"]
            target = state.get("target_column", None)
            result = run_analysis(dataset_path, target)
            state["result"] = result
            if result["success"]:
                state["steps_taken"].append("execute_analysis")
            else:
                state["error"] = result["error"]
            return state
    """
    logger.info(f"Starting full analysis: {dataset_path}")
    path = Path(dataset_path)

    # VALIDATION STAGE: Pre-flight checks before expensive operations
    # - File existence: Prevents "file not found" errors later
    # - Format validation: CSV vs other formats (xlsx, json, etc.)
    # - Returns early if validation fails to save processing time
    if not path.exists():
        logger.error(f"Dataset not found: {dataset_path}")
        return {"success": False, "error": f"Fichier non trouvé: {dataset_path}"}

    if path.suffix.lower() != ".csv":
        logger.error(f"Not a CSV file: {dataset_path}")
        return {"success": False, "error": f"Le fichier doit être un CSV: {dataset_path}"}

    # STAGE 1/5 — LOAD DATASET
    # Call dataset_loader to parse CSV with pandas (handles type inference, encoding detection)
    # Typical I/O: 100-500ms depending on file size
    # Errors: Logging issue, column naming conflicts, encoding problems
    logger.info("Stage 1/5: Loading dataset")
    load_result = load_dataset(dataset_path)
    if load_result.get("error") is not None:
      return {"success": False, "error": f"Erreur de chargement: {load_result.get('error')}"}

    df = load_result.get("dataframe")
    if df is None:
      return {"success": False, "error": "Dataset non chargé correctement"}
    rows, cols = df.shape
    logger.info(f"✓ Dataset loaded: {rows:,} rows, {cols} columns")

    # STAGE 2/5 — EXPLORATORY DATA ANALYSIS (EDA)
    # Generate statistical insights:
    # - Distribution analysis (normal, skewed, multimodal)
    # - Correlation detection (find relationships between features)
    # - Missing data patterns (percentage, location, imputation strategy)
    # - Outlier detection (statistical anomalies in single variables)
    # Timeouts: 500-2000ms typically
    # Graceful degradation: If EDA fails, continues with empty insights
    logger.info("Stage 2/5: Running EDA")
    try:
        eda_result = run_eda(load_result)
        eda_insights = eda_result.get("insights", [])
    except Exception as e:
        logger.warning(f"⚠ EDA failed: {e} (continuing without insights)")
        eda_insights = []

    # STAGE 3/5 — SUPERVISED LEARNING (AutoML + SHAP)
    # Only executed if target_column is specified and exists in DataFrame
    # Two sub-stages:
    # (a) AutoML: Tests 10+ algorithms, selects best performer on validation set
    #     - Examples: RandomForest, XGBoost, GradientBoosting, LightGBM
    #     - Typical time: 5-30 seconds (strongly depends on data size)
    # (b) SHAP: Calculates feature importance from best model
    #     - Interpretation: Which features drive predictions most
    #     - Typical time: 1-5 seconds
    # Skip condition: No target_column provided OR column not found in DataFrame
    best_model = None
    metrics = {}
    top_features = []

    if target_column and target_column in df.columns:
        logger.info(f"Stage 3/5: Running AutoML on target: {target_column}")
        try:
            # Run AutoML to find best model for this prediction task
            # Handles both regression (numeric target) and classification (categorical)
            automl_result = run_automl(df, target_column=target_column)
            if automl_result.get("success"):
                best_model = automl_result.get("best_model_name")
                metrics = automl_result.get("metrics", {})

                logger.info(f"  ✓ Best model: {best_model} (accuracy={metrics.get('accuracy', 'N/A')})")
                
                # Calculate SHAP feature importance on trained model
                # Shows which input variables contribute most to predictions
                # Used for model explainability and business insights
                logger.info("  Running SHAP explainability...")
                shap_result = explain_model(df, target_column=target_column)
                if shap_result.get("success"):
                    top_features = shap_result.get("top_features", [])[:5]
                    logger.info(f"  ✓ Top {len(top_features)} features identified")
        except Exception as e:
            logger.warning(f"⚠ AutoML/SHAP failed: {e} (continuing without model)")
    else:
        # Graceful skip: Not an error condition
        # AutoML requires explicit target column; without it, skips to anomaly detection
        logger.info("Stage 3/5: Skipping AutoML — no target column specified")

    # STAGE 4/5 — ANOMALY DETECTION (Data Quality Assessment)
    # Unsupervised detection of outliers and data quality issues
    # Methods: Isolation Forest, statistical bounds, clustering-based approaches
    # Outputs severity levels: HIGH (critical), MEDIUM (concerning), LOW (borderline)
    # Use case: Identify data entry errors, sensor failures, fraudulent records
    # Typical time: 1-3 seconds
    logger.info("Stage 4/5: Running anomaly detection")
    try:
        anomaly_result = detect_anomalies(load_result)
        severity = anomaly_result.get("severity_counts", {})
        anomalies = {
            "total": anomaly_result.get("anomaly_count", 0),
            "percentage": anomaly_result.get("anomaly_rate", 0),
            "high": severity.get("high", 0),
            "medium": severity.get("medium", 0),
            "low": severity.get("low", 0),
        }
        logger.info(f"✓ Detected {anomalies['total']} anomalies ({anomalies['percentage']:.2f}%)")
    except Exception as e:
        logger.warning(f"⚠ Anomaly detection failed: {e} (continuing without anomalies)")
        anomalies = {"total": 0, "percentage": 0}

    # STAGE 5/5 — SYNTHESIS (Build French Narrative)
    # Converts all structured results into human-readable report
    # Includes only the most relevant insights (top 3 features, top 3 metrics, etc.)
    # All text generated in French for CNIL compliance and user base alignment
    # Output: Multi-paragraph Markdown formatted for display
    logger.info("Stage 5/5: Building French narrative...")
    answer = _build_french_summary(
        path.name, rows, cols, eda_insights,
        best_model, metrics, top_features, anomalies
    )

    logger.info(f"✅ Analysis complete: {path.name} ({rows:,} rows)")

    # RETURN: All results packaged in structured dict for Agent state
    # success=True indicates pipeline completed (even if some engines failed gracefully)
    # Agent uses this dict to build conversation response
    return {
        "success": True,
        "dataset_path": dataset_path,
        "rows": rows,
        "columns": cols,
        "eda_insights": eda_insights,
        "best_model": best_model,
        "metrics": metrics,
        "top_features": top_features,
        "anomalies": anomalies,
        "answer": answer,
        "error": None
    }


def _build_french_summary(
    filename: str, rows: int, cols: int, eda_insights: list,
    best_model: str, metrics: dict, top_features: list, anomalies: dict
) -> str:
    """Build French narrative summary synthesizing all analysis engine outputs.

    Helper function that converts structured analysis results into human-readable
    Markdown-formatted French narrative for end-user consumption.

    Synthesis Logic:
    1. Dataset summary: Filename, dimensions (rows × columns)
    2. EDA insights: Top 3 statistical insights (if available)
    3. ML model: Best model name + top 3 metrics (if target provided)
    4. Feature importance: Top 3 most important variables from SHAP
    5. Anomalies: Summary of detected data quality issues by severity

    Args:
        filename (str):
            Name of analyzed CSV file (displayed to user).
            - Type: String (filename only, no path)
            - Example: "sales_2025.csv", "sensor_data.csv"
            - Usage: User context ("which file was analyzed")
            - Format: Wrapped in **bold** Markdown for emphasis

        rows (int):
            Number of data rows (from DataFrame.shape[0]).
            - Type: Positive integer
            - Example: 50000
            - Display: Formatted as locale number (50,000)

        cols (int):
            Number of columns/features (from DataFrame.shape[1]).
            - Type: Positive integer
            - Example: 15
            - Display: Shown as simple number

        eda_insights (list[str]):
            Statistical insights from EDA engine.
            - Type: List of French language strings
            - Example: ["Distribution normale", "Forte corrélation avec..."]
            - Handling: First 3 displayed if available
            - Empty: Entire insights section skipped if list is empty
            - Format: Displayed as bullet points with " - " prefix

        best_model (str or None):
            Name of best ML model from AutoML (or None).
            - Type: String or None
            - Example: "RandomForest", "XGBoost"
            - None handling: Entire ML section skipped
            - Display: Followed by metrics in parentheses

        metrics (dict):
            Performance metrics dictionary from best_model.
            - Type: {metric_name: score_value, ...}
            - Example: {"accuracy": 0.92, "f1": 0.85, "auc": 0.89}
            - Empty/None handling: Entire metrics skipped
            - Display: First 3 metrics shown, formatted to 3 decimals

        top_features (list[dict]):
            Feature importance from SHAP (format: [{"feature": str, "importance": float}])
            - Type: List of dicts with "feature" and "importance" keys
            - Example: [{"feature": "age", "importance": 0.35}, ...]
            - Empty handling: Entire features section skipped
            - Limit: First 3 features only shown
            - Display: Feature names joined with ", "

        anomalies (dict):
            Anomaly detection summary with severity breakdown.
            - Type: {"total": int, "percentage": float, "high": int, "medium": int, "low": int}
            - Example: {"total": 150, "percentage": 1.5, "high": 10, "medium": 40, "low": 100}
            - Empty/zero handling: "Aucune anomalie détectée." message shown
            - Display when total > 0: Multi-line summary with all severity levels
            - Format: "X anomalies (Y%) — Z critiques, M moyennes, L faibles."

    Returns:
        str: Multi-paragraph Markdown-formatted French narrative.
        - Type: String (never empty)
        - Minimum content: Filename + dimensions (always present)
        - Format: Multiple \\n-joined sections with **bold** headers
        - Language: 100% French
        - Encoding: UTF-8 (handles French accents: é, à, ç, etc.)

    Output Example:
        "J'ai analysé le fichier **sales_2025.csv** contenant 50,000 lignes et 15 colonnes.

        **Insights statistiques :**
        - Distribution normale pour la variable age
        - Forte corrélation entre revenue et customer_lifetime_value
        - 2.3% des données contiennent des valeurs manquantes

        **Modèle ML :** RandomForest (accuracy: 0.920, f1: 0.850, auc: 0.890)

        **Variables les plus importantes :** age, income, region

        **Anomalies détectées :** 35 anomalies (0.7% des données) — 
        2 critiques, 12 moyennes, 21 faibles."

    Design Notes:
        - Graceful degradation: Missing components (no model, no insights) don't break narrative
        - French-first: All templates in French for compliance and user base alignment
        - User-centric: Emphasizes actionable insights over technical details
        - Performance: O(n) where n = number of insights/features/metrics
        - Formatting: Uses Markdown bold (**text**) for section headers
        - Robustness: Handles None values, empty lists, missing dict keys

    Error Handling:
        - All parameters assumed valid (validated by run_analysis before calling)
        - Division by zero: percentage field accessed safely with .get()
        - Missing dict keys: Safe access with .get(key, default)
        - Non-existent list indices: Limited to [:3] slicing (safe)
    """

    parts = []
    parts.append(f"J'ai analysé le fichier **{filename}** contenant {rows:,} lignes et {cols} colonnes.")

    if eda_insights:
        parts.append("\n**Insights statistiques :**")
        for insight in eda_insights[:3]:
            parts.append(f"- {insight}")

    if best_model and metrics:
        metric_str = ", ".join(f"{k}: {v:.3f}" for k, v in list(metrics.items())[:3])
        parts.append(f"\n**Modèle ML :** {best_model} ({metric_str})")

    if top_features:
        features_str = ", ".join(f["feature"] for f in top_features[:3])
        parts.append(f"\n**Variables les plus importantes :** {features_str}")

    if anomalies.get("total", 0) > 0:
        parts.append(
            f"\n**Anomalies détectées :** {anomalies['total']} anomalies "
            f"({anomalies['percentage']:.1f}% des données) — "
            f"{anomalies.get('high', 0)} critiques, "
            f"{anomalies.get('medium', 0)} moyennes, "
            f"{anomalies.get('low', 0)} faibles."
        )
    else:
        parts.append("\n**Anomalies :** Aucune anomalie détectée.")

    return "\n".join(parts)