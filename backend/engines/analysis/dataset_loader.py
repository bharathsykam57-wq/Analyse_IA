"""Dataset loading and analysis module for processing CSV files.

This module provides utilities for safely loading CSV files with flexible encoding
detection, column type classification, and basic statistical profiling. It handles
large datasets by implementing chunked loading when necessary and provides detailed
metadata about loaded data for downstream analysis.

Typical usage:
    result = load_dataset('path/to/file.csv')
    if result['error']:
        print(f"Failed to load: {result['error']}")
    else:
        df = result['dataframe']
        stats = result['stats']
"""
import os
import logging
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/analyse_ia.log')
    ]
)

logger = logging.getLogger(__name__)

# Common text encodings used in French government and institutional data sources.
# Ordered by likelihood to reduce detection attempts on typical data.
SUPPORTED_ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']

# Maximum number of rows to load completely into memory in a single operation.
# Larger datasets are loaded in chunks to prevent memory exhaustion.
MAX_ROWS_FULL_LOAD = 100_000

# Number of rows to process per chunk when handling large datasets.
CHUNK_SIZE = 10_000


def detect_encoding(file_path: str) -> str:
    """Detect the text encoding of a file by attempting to read with known encodings.

    Attempts to read a sample of the file using each encoding in SUPPORTED_ENCODINGS.
    This is particularly important for French government and institutional data,
    which frequently uses latin-1 or iso-8859-1 encodings despite utf-8 being the
    modern standard.

    The function tries encodings in priority order (utf-8 first, fastest), stopping
    at the first successful decode. A 1KB sample is sufficient to detect encoding
    for typical CSV files.

    Args:
        file_path: Absolute or relative path to the file to analyze.

    Returns:
        The detected encoding name (e.g., 'utf-8', 'latin-1'). Defaults to 'utf-8'
        if no encoding can be detected (rarely happens with well-formed files).

    Raises:
        No exceptions are raised; encoding detection failures log a warning and
        default to 'utf-8' for graceful degradation.

    Examples:
        encoding = detect_encoding('data/french_records.csv')  # Returns 'latin-1'
        encoding = detect_encoding('data/modern_data.csv')      # Returns 'utf-8'
    """
    for encoding in SUPPORTED_ENCODINGS:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(1024)  # Try reading first 1KB to detect encoding
            logger.info(f"Detected encoding: {encoding} for {Path(file_path).name}")
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            # This encoding doesn't work, try the next one
            continue

    # Fallback: if no encoding works, default to utf-8 and log warning
    logger.warning(f"Could not detect encoding for {file_path}, defaulting to utf-8")
    return 'utf-8'


def get_column_types(df: pd.DataFrame) -> dict:
    """Classify DataFrame columns into semantic types for analysis purposes.

    Examines each column and categorizes it as numeric, categorical, datetime,
    text, or unknown. For object-type columns, attempts datetime parsing first
    before distinguishing between categorical and text.

    Categorical Classification Logic:
    Uses both absolute and relative thresholds to handle datasets of varying sizes:
    - Columns with ≤20 unique values are categorical (e.g., gender, region)
    - For datasets >50 rows: columns with <20% unique values are categorical
    - This prevents small datasets from incorrectly classifying all columns as text

    Args:
        df: A pandas DataFrame to analyze. Works with any size or column types.

    Returns:
        A dictionary with keys 'numeric', 'categorical', 'datetime', 'text',
        and 'unknown', each mapping to a list of column names belonging to
        that type.

    Examples:
        Input columns: [price (150000-500000), city (Paris, Lyon, Mars), birth_date]
        Output: numeric=[price], categorical=[city], datetime=[birth_date]
    """
    column_types = {
        'numeric': [],
        'categorical': [],
        'datetime': [],
        'text': [],
        'unknown': []
    }

    for col in df.columns:
        # Check for native numeric types (int, float, etc.)
        if pd.api.types.is_numeric_dtype(df[col]):
            column_types['numeric'].append(col)
        # Check for native datetime types (datetime64, etc.)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            column_types['datetime'].append(col)
        # For object-type and string-type columns, attempt to infer the true semantic type.
        # pandas 3.0+ uses dtype 'str' for string columns; older versions use 'object'.
        elif df[col].dtype == 'object' or df[col].dtype == 'str' or pd.api.types.is_string_dtype(df[col]):
            # Attempt to detect datetime values stored as strings (common in CSV imports).
            # Uses flexible datetime parsing to handle various formats and handle warnings
            # raised by newer pandas versions when partial parsing succeeds.
            try:
                parsed = pd.to_datetime(df[col], format='mixed', dayfirst=False)
                if parsed.notna().sum() > 0:
                    column_types['datetime'].append(col)
                    continue
            except Exception:
                # Column values are not datetime-parseable; continue to categorical/text classification
                pass

            # Classify as categorical or text based on cardinality.
            # Uses absolute count (≤20 unique values) for small datasets to prevent
            # ratio-based bias, and relative threshold (20% for datasets >50 rows)
            # for larger datasets. This handles both sparse and dense data appropriately.
            n_unique = df[col].nunique()
            n_rows = len(df)

            if n_unique <= 20 or (n_rows > 50 and n_unique / n_rows < 0.2):
                column_types['categorical'].append(col)
            else:
                column_types['text'].append(col)
        else:
            # Unrecognized dtype that doesn't fit standard categories.
            # Marked for manual inspection or special handling.
            column_types['unknown'].append(col)

    return column_types


def get_basic_stats(df: pd.DataFrame) -> dict:
    """Compute summary statistics about a DataFrame for data profiling.

    Generates a comprehensive overview of the dataset including row count,
    column count, column names, missing value analysis, memory footprint,
    and duplicate row detection. This metadata is computed for every loaded
    dataset to support data quality assessment and downstream processing.

    Statistics Computed:
    - Basic dimensions: row and column counts
    - Column names: list of all column identifiers
    - Missing value analysis: both absolute counts and percentages per column
    - Memory footprint: total memory usage in MB (using deep analysis)
    - Data quality: count of completely duplicate rows

    Args:
        df: A pandas DataFrame to profile. Works with any size.

    Returns:
        A dictionary containing:
        - 'rows': Number of rows in the DataFrame
        - 'columns': Number of columns
        - 'column_names': List of column names
        - 'missing_values': Count of null/NaN values per column
        - 'missing_percentage': Percentage of missing values per column (rounded to 2 decimals)
        - 'memory_usage_mb': Total memory usage in megabytes
        - 'duplicate_rows': Count of completely duplicate rows

    Examples:
        Input: 1000 x 10 DataFrame with 50 NaN values
        Output: {'rows': 1000, 'columns': 10, 'memory_usage_mb': 0.08, ...}
    """
    # Calculate missing values for each column
    missing_counts = df.isnull().sum()
    total_rows = len(df)
    
    stats = {
        'rows': total_rows,
        'columns': len(df.columns),
        'column_names': list(df.columns),
        'missing_values': missing_counts.to_dict(),
        # Calculate percentage and round to 2 decimals for readability
        'missing_percentage': (missing_counts / total_rows * 100).round(2).to_dict(),
        # Use deep=True to include object dtype sizes accurately
        'memory_usage_mb': round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        # Count rows that are complete duplicates of another row
        'duplicate_rows': int(df.duplicated().sum())
    }
    return stats


def load_dataset(file_path: str) -> dict:
    """Load a CSV file with robust error handling, encoding detection, and metadata.

    Safely loads CSV files with automatic encoding detection, file validation,
    and intelligent chunking for large datasets. All errors are captured and
    returned in the result dictionary rather than raised as exceptions, allowing
    callers to handle failures gracefully without try/except blocks.

    File validation includes:
    - Existence check
    - CSV extension verification
    - Non-empty file check

    Large dataset handling:
    - Files with >100,000 rows are partially loaded (first 100,000 rows)
    - The 'truncated' flag indicates whether the full file or a sample was loaded

    Args:
        file_path: Absolute or relative path to a CSV file.

    Returns:
        A dictionary with the following keys:
        - 'dataframe' (pd.DataFrame | None): Loaded data or None if loading failed
        - 'stats' (dict | None): Basic statistics from get_basic_stats()
        - 'column_types' (dict | None): Column classifications from get_column_types()
        - 'encoding' (str | None): Detected text encoding used for the file
        - 'file_name' (str): Original filename extracted from file_path
        - 'truncated' (bool): True if only a sample was loaded due to size limits
        - 'error' (str | None): Error message if loading failed, None on success

    The function never raises exceptions. All errors are logged and returned
    in the 'error' field. Successful loads have error=None.
    """
    result = {
        'dataframe': None,
        'stats': None,
        'column_types': None,
        'encoding': None,
        'truncated': False,
        'file_name': Path(file_path).name,
        'error': None
    }

    # Validate that the specified file exists before attempting to open it.
    if not os.path.exists(file_path):
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result

    # Ensure the file has a CSV extension to prevent accidental mishandling of other formats.
    if not file_path.endswith('.csv'):
        error_msg = f"File must be a CSV: {file_path}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result

    # Reject empty files early to avoid pandas parsing errors and unnecessary processing.
    if os.path.getsize(file_path) == 0:
        error_msg = f"File is empty: {file_path}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result

    try:
        # STEP 1: Detect the file's character encoding to handle various data sources correctly.
        # This is critical for French government data which often uses latin-1
        encoding = detect_encoding(file_path)
        result['encoding'] = encoding

        # STEP 2: Count total rows first without loading entire file to determine loading strategy.
        # This allows for intelligent decision-making about memory usage
        # Subtract 1 from line count to exclude the header row.
        with open(file_path, 'r', encoding=encoding) as f:
            row_count = sum(1 for _ in f) - 1

        logger.info(f"File has {row_count:,} rows: {Path(file_path).name}")

        # STEP 3: Load dataset with appropriate strategy based on size
        # Load full dataset if it fits within memory constraints (≤100,000 rows).
        if row_count <= MAX_ROWS_FULL_LOAD:
            df = pd.read_csv(file_path, encoding=encoding)
            result['truncated'] = False
            logger.info(f"Loaded full dataset: {row_count:,} rows")
        else:
            # For large datasets, load only the first chunk for inspection and metadata.
            # The full dataset can be processed later using chunked iteration if needed
            # This prevents memory exhaustion while still providing data structure info
            df = pd.read_csv(file_path, encoding=encoding, nrows=MAX_ROWS_FULL_LOAD)
            result['truncated'] = True
            logger.warning(
                f"Dataset has {row_count:,} rows. "
                f"Loaded first {MAX_ROWS_FULL_LOAD:,} for inspection. "
                f"Full analysis will use chunked processing."
            )

        # STEP 4: Populate result dictionary with dataframe and derived metadata.
        # This includes statistics, column type classification, and file metadata
        result['dataframe'] = df
        result['stats'] = get_basic_stats(df)
        result['column_types'] = get_column_types(df)

        logger.info(
            f"Successfully loaded {result['file_name']} | "
            f"{result['stats']['rows']:,} rows | "
            f"{result['stats']['columns']} columns | "
            f"{result['stats']['memory_usage_mb']}MB"
        )

        return result

    except pd.errors.EmptyDataError:
        # Pandas raised EmptyDataError, indicating CSV has headers but no data rows.
        # This catches files that parse as valid CSV but have no content rows
        error_msg = f"CSV file has no data: {file_path}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result

    except pd.errors.ParserError as e:
        # Pandas encountered malformed CSV content (e.g., mismatched delimiters, bad encoding).
        # This catches structural CSV problems
        error_msg = f"CSV parsing error: {str(e)}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result

    except Exception as e:
        # Capture any unexpected errors to ensure function never fails silently.
        # This provides graceful error handling for edge cases
        error_msg = f"Unexpected error loading {file_path}: {str(e)}"
        logger.error(error_msg)
        result['error'] = error_msg
        return result