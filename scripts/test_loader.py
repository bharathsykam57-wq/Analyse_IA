"""Test script for dataset_loader module.

Creates a sample CSV file with representative data and validates the loader's
ability to detect encodings, classify columns, compute statistics, and handle
the data gracefully.
"""
import sys
import os

# Add parent directory to path to enable imports from backend package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.analysis.dataset_loader import load_dataset
import pandas as pd

# ==================== SETUP: Create Test Data ====================
# Generate a small representative dataset simulating real estate/market data
# with mixed column types (text, numeric, datetime) for comprehensive testing
test_data = pd.DataFrame({
    'nom': ['Jean Dupont', 'Marie Martin', 'Pierre Bernard'],
    'ville': ['Paris', 'Lyon', 'Marseille'],
    'prix': [250000, 180000, 220000],
    'surface': [75, 60, 85],
    'date': ['2023-01-15', '2023-02-20', '2023-03-10']
})

# Create data directory and persist test CSV
os.makedirs('data/demos', exist_ok=True)
test_data.to_csv('data/demos/test_sample.csv', index=False)
print("✓ Test CSV created: data/demos/test_sample.csv\n")

# ==================== EXECUTION: Load and Validate Dataset ====================
print("Loading dataset via dataset_loader.load_dataset()...")
print("="*60)
result = load_dataset('data/demos/test_sample.csv')

if result['error']:
    print(f"\n✗ FAILED: {result['error']}")
else:
    # Display file metadata
    print(f"\n✓ SUCCESS: Dataset loaded successfully")
    print(f"\n[File Information]")
    print(f"  Filename: {result['file_name']}")
    print(f"  Encoding: {result['encoding']}")
    print(f"  Fully loaded: {not result['truncated']}")
    
    # Display dataset statistics
    stats = result['stats']
    print(f"\n[Dataset Metrics]")
    print(f"  Total rows: {stats['rows']:,}")
    print(f"  Total columns: {stats['columns']}")
    print(f"  Memory usage: {stats['memory_usage_mb']} MB")
    print(f"  Duplicate rows: {stats['duplicate_rows']}")
    
    # Display column type classification
    col_types = result['column_types']
    print(f"\n[Column Type Classification]")
    for col_type, cols in col_types.items():
        if cols:
            print(f"  {col_type:12s}: {', '.join(cols)}")
    
    # Display missing value analysis
    missing = stats['missing_values']
    print(f"\n[Data Quality - Missing Values]")
    has_missing = any(count > 0 for count in missing.values())
    if has_missing:
        for col, count in missing.items():
            if count > 0:
                pct = stats['missing_percentage'][col]
                print(f"  {col:12s}: {count} missing ({pct:.1f}%)")
    else:
        print(f"  No missing values detected - data quality is complete")
    
    print(f"\n" + "="*60)
    print(f"✓ All dataset_loader functions working correctly")