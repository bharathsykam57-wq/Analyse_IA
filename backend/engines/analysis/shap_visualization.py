"""SHAP visualization utilities for model explainability plots.

Generates interactive and static visualizations of SHAP values for model interpretability:
- Feature importance bar plots (global importance)
- Waterfall plots (local sample explanations)
- Dependency plots (feature interaction analysis)
- Summary plots (SHAP value distributions)

All plots are generated as Plotly JSON for frontend display and as PNG for export/documentation.

COMPLIANCE: Supports EU AI Act Article 13 transparency through visual explanations
"""

import logging
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def shap_importance_bar(global_importance: List[Dict]) -> Dict:
    """Generate interactive bar plot for SHAP feature importance.

    Shows top features ranked by average absolute SHAP values (how much each feature
    on average changes model predictions).

    Args:
        global_importance: List of dicts from explain_model()['global_importance']
                          [{feature: str, importance: float, importance_percentage: float}, ...]

    Returns:
        Plotly figure JSON dict ready for frontend rendering
    """
    try:
        if not global_importance:
            logger.warning("Empty global_importance list provided")
            return {"error": "No feature importance data"}

        # Extract top 10 features for clarity
        top_features = global_importance[:10]
        features = [item["feature"] for item in top_features]
        importance = [item["importance_percentage"] for item in top_features]

        fig = go.Figure(
            data=[
                go.Bar(
                    x=importance,
                    y=features,
                    orientation="h",
                    marker=dict(
                        color=importance,
                        colorscale="Viridis",
                        showscale=True,
                        colorbar=dict(title="Importance %")
                    ),
                    text=[f"{v:.1f}%" for v in importance],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Importance: %{x:.1f}%<extra></extra>"
                )
            ]
        )

        fig.update_layout(
            title="SHAP Feature Importance (Top 10)",
            xaxis_title="Importance (%)",
            yaxis_title="Feature",
            height=400,
            showlegend=False,
            hovermode="closest",
            template="plotly_white"
        )

        return json.loads(fig.to_json())

    except Exception as e:
        logger.error(f"Error generating importance bar plot: {e}")
        return {"error": str(e)}


def shap_waterfall_plot(local_explanation: Dict, sample_index: int = 0) -> Dict:
    """Generate waterfall plot for local SHAP explanation.

    Shows how individual feature contributions add up to final prediction.
    Formula: baseline + feature_1_contribution + feature_2_contribution + ... = prediction

    Args:
        local_explanation: Single element from explain_model()['local_explanations']
                          {prediction: float, baseline: float, contributions: [{...}, ...]}
        sample_index: Sample number (for display labels)

    Returns:
        Plotly figure JSON dict
    """
    try:
        baseline = local_explanation["baseline"]
        prediction = local_explanation["prediction"]
        contributions = local_explanation["contributions"]

        if not contributions:
            logger.warning("No contributions in local explanation")
            return {"error": "No contribution data"}

        # Sort by absolute contribution for visibility
        sorted_contrib = sorted(
            contributions,
            key=lambda x: abs(x["shap_contribution"]),
            reverse=True
        )[:5]  # Top 5 contributions

    # Build waterfall data
        labels = ["Baseline"] + [c["feature"] for c in sorted_contrib] + ["Prediction"]
        values = [0] + [c["shap_contribution"] for c in sorted_contrib] + [0]
        
        # Waterfall uses "measure" to specify total vs relative
        measures = ["total"] + ["relative"] * len(sorted_contrib) + ["total"]

        # Calculate text positions based on cumulative sum
        text_values = [baseline] + [
            baseline + sum([c["shap_contribution"] for c in sorted_contrib[:i+1]])
            for i in range(len(sorted_contrib))
        ] + [prediction]

        colors = ["blue"] + [
            "green" if v > 0 else "red" for v in values[1:-1]
        ] + ["darkgreen"]

        fig = go.Figure(
            go.Waterfall(
                name="SHAP Prediction",
                x=labels,
                y=values,
                measure=measures,
                text=[f"€{v:,.0f}" if i == 0 or i == len(text_values)-1 else f"{v:+,.0f}" 
                      for i, v in enumerate(text_values)],
                textposition="outside",
                connector={"line": {"color": "gray", "dash": "dot"}},
                marker={"color": colors},
                hovertemplate="<b>%{x}</b><br>Value: €%{customdata:,.0f}<extra></extra>",
                customdata=values
            )
        )

        fig.update_layout(
            title=f"SHAP Waterfall: Sample {sample_index} (Baseline €{baseline:,.0f} → Prediction €{prediction:+,.0f})",
            yaxis_title="Contribution (€)",
            height=500,
            template="plotly_white"
        )

        return json.loads(fig.to_json())

    except Exception as e:
        logger.error(f"Error generating waterfall plot: {e}")
        return {"error": str(e)}


def shap_force_plot_data(local_explanation: Dict) -> Dict:
    """Convert SHAP local explanation to force plot format (base_value, shap_values, data).

    Generates data structure compatible with SHAP force plot visualization:
    - base_value: Baseline prediction
    - shap_values: Individual feature contributions
    - data: Feature values
    - feature_names: Feature names

    Args:
        local_explanation: Single element from explain_model()['local_explanations']

    Returns:
        Dict with force_plot compatible data structure
    """
    try:
        baseline = local_explanation["baseline"]
        contributions = local_explanation["contributions"]

        if not contributions:
            return {"error": "No contributions"}

        feature_names = [c["feature"] for c in contributions]
        shap_values = [c["shap_contribution"] for c in contributions]
        values = [c["value"] for c in contributions]

        return {
            "base_value": baseline,
            "shap_values": shap_values,
            "data": values,
            "feature_names": feature_names,
            "prediction": local_explanation["prediction"]
        }

    except Exception as e:
        logger.error(f"Error generating force plot data: {e}")
        return {"error": str(e)}


def shap_summary_statistics(global_importance: List[Dict]) -> Dict:
    """Generate summary statistics of feature importance distribution.

    Args:
        global_importance: List from explain_model()['global_importance']

    Returns:
        Dict with summary stats (mean, median, std, top_3, coverage)
    """
    try:
        if not global_importance:
            return {"error": "Empty importance list"}

        importances = [item["importance"] for item in global_importance]

        total_importance = sum(importances)
        top_3_importance = sum(importances[:3])
        coverage_pct = (top_3_importance / total_importance * 100) if total_importance > 0 else 0

        return {
            "total_features": len(global_importance),
            "mean_importance": round(np.mean(importances), 4),
            "median_importance": round(float(np.median(importances)), 4),
            "std_importance": round(float(np.std(importances)), 4),
            "top_3_features": [item["feature"] for item in global_importance[:3]],
            "top_3_coverage_percent": round(coverage_pct, 1),
            "top_feature": global_importance[0]["feature"] if global_importance else None,
            "top_feature_importance": round(global_importance[0]["importance"], 4) if global_importance else None
        }

    except Exception as e:
        logger.error(f"Error computing summary statistics: {e}")
        return {"error": str(e)}
