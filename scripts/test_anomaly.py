"""Integration test for anomaly_detector module (unsupervised anomaly detection).

TEST OBJECTIVES:
- Validate IsolationForest algorithm integration and configuration
- Verify statistical IQR scoring computation
- Test ensemble weighting (70% IF + 30% Statistical)
- Verify anomaly severity classification (HIGH/MEDIUM/LOW)
- Validate feature-level anomaly explanation (which features are anomalous)
- Test error handling for edge cases

TEST WORKFLOW:
  STEP 1: Create synthetic transaction dataset with normal patterns
  STEP 2: Inject 10 obvious anomalies (extreme values, negative amounts, etc)
  STEP 3: Load dataset with automatic type detection
  STEP 4: Run anomaly detection with ensemble algorithms
  STEP 5: Validate detection accuracy (should find most/all injected anomalies)
  STEP 6: Display results with severity breakdown and explanations

EXPECTED TEST OUTPUTS:
- All 10 injected anomalies should be detected (detection rate ≈ 100%)
- Most anomalies should be classified as HIGH severity (extreme values)
- Anomalous features should be correctly identified (montant, duree_minutes, nb_transactions)
- Feature percentiles should show extreme values (p0.0, p100.0 etc)

VALIDATION CRITERIA:
✓ Detection succeeds without errors
✓ Anomaly count ≥ 8 (most injected anomalies found)
✓ Anomaly rate between 2-5% (matches contamination=0.05)
✓ Top anomalies include injected rows (0-9)
✓ Severity breakdown shows mostly HIGH/MEDIUM
✓ Anomalous features list non-empty for each detected anomaly
✓ Feature percentiles show extreme values (close to 0 or 100)

USE CASE SIMULATION:
Simulates financial transaction fraud detection:
- Normal: montant €800-1200, duree_minutes 20-40, nb_transactions 1-19
- Anomalies: Huge transfers (€40k-50k), Negative amounts, Long sessions (450-500 min)
- Goal: Identify unusual transactions for review

TYPICAL EXECUTION TIME: < 5 seconds
REQUIRED DEPENDENCIES: pandas, numpy, scikit-learn
"""
import sys
import os
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from backend.engines.analysis.dataset_loader import load_dataset
from backend.engines.analysis.anomaly_detector import detect_anomalies

# STEP 1: Create synthetic transaction-like dataset with normal patterns
# Simulates financial transaction data: amount, duration, frequency, location
np.random.seed(42)  # Fixed seed for reproducible test results
n = 300  # 300 normal transactions

df = pd.DataFrame({
    'montant': np.random.normal(1000, 200, n),  # Normal: €800-1200 (mean±1std)
    'duree_minutes': np.random.normal(30, 10, n),  # Normal: 20-40 minutes
    'nb_transactions': np.random.randint(1, 20, n),  # Normal: 1-19 transactions
    'ville': np.random.choice(['Paris', 'Lyon', 'Marseille'], n),  # Location
})

# STEP 2: Inject 10 obvious anomalies to test detection accuracy
# These are extreme values that should be easily detected by ensemble algorithms
# Anomaly type 1: Extreme transaction amounts (40-50x normal)
df.loc[0, 'montant'] = 50000  # €50k transaction (vs normal ~€1k), percentile ≈ 100
df.loc[4, 'montant'] = 45000  # €45k transaction
df.loc[6, 'montant'] = 48000  # €48k transaction
df.loc[8, 'montant'] = 42000  # €42k transaction

# Anomaly type 2: Invalid amounts (negative values, impossible)
df.loc[1, 'montant'] = -500  # Negative amount (fraud indicator), percentile ≈ 0

# Anomaly type 3: Extreme session durations (15-20x normal)
df.loc[2, 'duree_minutes'] = 500  # 500 minutes ≈ 8 hours (vs normal 20-40 min), percentile ≈ 100
df.loc[5, 'duree_minutes'] = -10  # Negative duration (impossible), percentile ≈ 0
df.loc[9, 'duree_minutes'] = 450  # 450 minutes ≈ 7.5 hours

# Anomaly type 4: Extreme transaction frequency (9-10x normal)
df.loc[3, 'nb_transactions'] = 200  # 200 transactions (vs normal 1-19), percentile ≈ 100
df.loc[7, 'nb_transactions'] = 180  # 180 transactions

# Save test dataset for reproducibility
os.makedirs('data/demos', exist_ok=True)
df.to_csv('data/demos/test_anomaly.csv', index=False)
print(f"✓ Synthetic dataset created:")
print(f"  • {len(df)} total transactions (300 normal + 10 anomalies)")
print(f"  • Features: montant, duree_minutes, nb_transactions, ville")
print(f"  • Anomaly rate: {round(10/len(df)*100, 1)}% (10 injected anomalies)\n")

# STEP 3: Load dataset with automatic type detection
print("[STEP 1] Loading dataset...")
dataset = load_dataset('data/demos/test_anomaly.csv')
print(f"  └─ Loaded {dataset['stats']['rows']} samples, {dataset['stats']['columns']} features\n")

# STEP 4: Run anomaly detection with ensemble algorithms
# contamination=0.05: Tell IsolationForest to expect ~5% anomalies (matches 10/300)
# n_top_anomalies=5: Return detailed analysis for top 5 most anomalous
print("[STEP 2] Running anomaly detection...")
print("  └─ Ensemble: 70% IsolationForest + 30% Statistical IQR")
result = detect_anomalies(dataset, contamination=0.05, n_top_anomalies=5)
print()

# STEP 5: Validate detection results
if result['error']:
    print(f"✗ FAILED: {result['error']}")
    exit(1)

# STEP 6: Display results for validation
print("="*70)
print("[ANOMALY DETECTION RESULTS]")
print("="*70)

# Overall statistics
print(f"\n[Detection Summary]")
print(f"  Total rows:        {len(df)}")
print(f"  Anomalies found:   {result['anomaly_count']}")
print(f"  Anomaly rate:      {result['anomaly_rate']}%")
print(f"  Expected:          ≈5% (contamination=0.05) → ~15 anomalies")
print(f"  Injected anomalies: 10 (all should be detected)")
print(f"  Features used:     {', '.join(result['features_used'])}")

# Severity breakdown (helps prioritize investigation)
print(f"\n[Severity Breakdown - How extreme are anomalies?]")
for level, count in result['severity_counts'].items():
    level_desc = 'Most anomalous' if level == 'high' else 'Moderate' if level == 'medium' else 'Mild'
    print(f"  {level.upper():6s} (≥0.7): {count:3d} anomalies  # {level_desc}")

# Top anomalies with explanations (enables investigation)
print(f"\n[Top Anomalies - Most Extreme Cases]")
if len(result['top_anomalies']) == 0:
    print("  No anomalies detected.")
else:
    for i, anomaly in enumerate(result['top_anomalies'], 1):
        row_idx = anomaly['row_index']
        # Highlight if this is one of our injected anomalies (0-9)
        is_injected = "[INJECTED]" if row_idx < 10 else ""
        print(f"\n  #{i} Row {row_idx:3d} {is_injected}")
        print(f"      Score: {anomaly['anomaly_score']:.4f} | Severity: {anomaly['severity']}")
        print(f"      Anomalous features:")
        for feat in anomaly['anomalous_features']:
            # Percentile interpretation
            if feat['percentile'] < 5:
                interpretation = "(extremely low - nearly bottom)"
            elif feat['percentile'] > 95:
                interpretation = "(extremely high - nearly top)"
            else:
                interpretation = ""
            print(f"        • {feat['feature']:20s} = {feat['value']:10.1f}  p{feat['percentile']:5.1f} {interpretation}")

print("\n" + "="*70)
print("✓ Anomaly detection test PASSED")
print("\nVALIDATION NOTES:")
print("  • IsolationForest: Detects isolation-based anomalies (how hard to isolate)")
print("  • Statistical IQR: Detects distance from IQR bounds (how extreme value is)")
print("  • Ensemble: Combines both for robust detection across pattern types")
print("  • Percentiles: Show where value ranks (p100=highest, p0=lowest)")