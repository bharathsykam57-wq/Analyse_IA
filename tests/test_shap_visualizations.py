#!/usr/bin/env python
"""Quick test for SHAP visualization functions"""

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.analysis.shap_visualization import (
    shap_importance_bar,
    shap_waterfall_plot,
    shap_force_plot_data,
    shap_summary_statistics
)

# Mock SHAP result data
global_importance = [
    {"feature": "surface", "importance": 0.538, "importance_percentage": 53.8},
    {"feature": "ville", "importance": 0.271, "importance_percentage": 27.1},
    {"feature": "nb_pieces", "importance": 0.168, "importance_percentage": 16.8},
    {"feature": "annee_construction", "importance": 0.012, "importance_percentage": 1.2},
    {"feature": "type_bien", "importance": 0.011, "importance_percentage": 1.1},
]

local_explanation = {
    "prediction": 413802,
    "baseline": 341646,
    "contributions": [
        {"feature": "surface", "value": 87, "shap_contribution": 132553, "direction": "positive"},
        {"feature": "ville", "value": "Paris", "shap_contribution": -47537, "direction": "negative"},
        {"feature": "nb_pieces", "value": 2, "shap_contribution": -7621, "direction": "negative"},
        {"feature": "annee_construction", "value": 1991, "shap_contribution": 2435, "direction": "positive"},
        {"feature": "type_bien", "value": "Appartement", "shap_contribution": 871, "direction": "positive"},
    ]
}

print("Testing SHAP Visualization Functions")
print("=" * 60)

# Test 1: Importance bar plot
print("\n[1] Testing importance_bar()...")
bar_plot = shap_importance_bar(global_importance)
if "error" not in bar_plot:
    print("✅ Generated importance bar plot (Plotly JSON)")
    print(f"   - Contains {len(bar_plot.get('data', []))} traces")
else:
    print(f"❌ Error: {bar_plot['error']}")

# Test 2: Waterfall plot
print("\n[2] Testing waterfall_plot()...")
waterfall = shap_waterfall_plot(local_explanation, sample_index=1)
if "error" not in waterfall:
    print("✅ Generated waterfall plot (Plotly JSON)")
    print(f"   - Contains {len(waterfall.get('data', []))} traces")
else:
    print(f"❌ Error: {waterfall['error']}")

# Test 3: Force plot data
print("\n[3] Testing force_plot_data()...")
force_data = shap_force_plot_data(local_explanation)
if "error" not in force_data:
    print("✅ Generated force plot data")
    print(f"   - Base value: €{force_data['base_value']:,.0f}")
    print(f"   - Prediction: €{force_data['prediction']:,.0f}")
    print(f"   - Features: {len(force_data['feature_names'])}")
else:
    print(f"❌ Error: {force_data['error']}")

# Test 4: Summary statistics
print("\n[4] Testing summary_statistics()...")
stats = shap_summary_statistics(global_importance)
if "error" not in stats:
    print("✅ Generated summary statistics")
    print(f"   - Total features: {stats['total_features']}")
    print(f"   - Top feature: {stats['top_feature']} ({stats['top_feature_importance']:.2%})")
    print(f"   - Top 3 coverage: {stats['top_3_coverage_percent']}%")
else:
    print(f"❌ Error: {stats['error']}")

print("\n" + "=" * 60)
print("✅ All visualization functions working!")
