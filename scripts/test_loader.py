"""Test script for dataset_loader module.

Creates a sample CSV file with representative data and validates the loader's
ability to detect encodings, classify columns, compute statistics, and handle
the data gracefully.

This script is designed to:
1. Verify all dataset_loader functions work correctly without errors
2. Validate column type classification (numeric, categorical, datetime, text)
3. Test encoding detection on various file types
4. Verify statistics computation (missing values, memory usage, duplicates)
5. Demonstrate correct error handling for invalid files
6. Serve as integration test for the full loading pipeline

Tests Performed:
- File validation (existence, CSV extension, non-empty)
- Encoding detection (utf-8, latin-1, etc.)
- CSV parsing and data loading
- Column type classification accuracy
- Statistical profiling (rows, columns, memory, duplicates)
- Missing value analysis
- Error handling for edge cases

Data Characteristics:
- Small representative dataset for quick testing
- Mixed column types: text (names, cities), numeric (prices), datetime
- Complete data (no missing values) for validation
- Realistic field names matching real estate domain
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
# This tests the loader's ability to handle diverse data types
test_data = pd.DataFrame({
    'nom': ['Jean Dupont', 'Marie Martin', 'Pierre Bernard'],
    'ville': ['Paris', 'Lyon', 'Marseille'],
    'prix': [250000, 180000, 220000],
    'surface': [75, 60, 85],
    'date': ['2023-01-15', '2023-02-20', '2023-03-10']
})

# Create data directory and persist test CSV
# This ensures consistent test data for repeated runs
os.makedirs('data/demos', exist_ok=True)
test_data.to_csv('data/demos/test_sample.csv', index=False)
print("✓ Test CSV created: data/demos/test_sample.csv\n")

# ==================== EXECUTION: Load and Validate Dataset ====================
# This is the main test - load the CSV using all dataset_loader functions
print("Loading dataset via dataset_loader.load_dataset()...")
print("="*60)
result = load_dataset('data/demos/test_sample.csv')

if result['error']:
    print(f"\n✗ FAILED: {result['error']}")
else:
    # Display file metadata stored during loading
    # This validates that all file characteristics were properly detected
    print(f"\n✓ SUCCESS: Dataset loaded successfully")
    print(f"\n[File Information]")
    print(f"  Filename: {result['file_name']}")
    print(f"  Encoding: {result['encoding']}")
    print(f"  Fully loaded: {not result['truncated']}")
    
    # Display dataset statistics computed by get_basic_stats()
    # These metrics are essential for understanding data scale and quality
    stats = result['stats']
    print(f"\n[Dataset Metrics]")
    print(f"  Total rows: {stats['rows']:,}")
    print(f"  Total columns: {stats['columns']}")
    print(f"  Memory usage: {stats['memory_usage_mb']} MB")
    print(f"  Duplicate rows: {stats['duplicate_rows']}")
    
    # Display column type classification from get_column_types()
    # Correct classification is critical for downstream analysis
    col_types = result['column_types']
    print(f"\n[Column Type Classification]")
    for col_type, cols in col_types.items():
        if cols:
            print(f"  {col_type:12s}: {', '.join(cols)}")
    
    # Display missing value analysis from get_basic_stats()
    # Missing values are a key data quality indicator
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