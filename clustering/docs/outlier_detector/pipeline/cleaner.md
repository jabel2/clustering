# cleaner.py - Data Cleaning Utilities

**File**: `src/outlier_detector/pipeline/cleaner.py`
**Module**: `outlier_detector.pipeline`
**Purpose**: Clean raw DataFrames by handling missing values, coercing types, and separating ID columns.

---

## Overview

`cleaner.py` prepares raw data for feature engineering. It performs three key operations:
1. Extracts and separates the ID column (if specified) so it is not processed as a feature.
2. Fills missing values using statistically appropriate strategies.
3. Coerces columns to their correct types (e.g., string columns that contain numbers, boolean-like values).

---

## Public API

### `clean_data(df, id_column=None, exclude_columns=None) -> tuple[pd.DataFrame, pd.Series | None]`

Cleans a DataFrame for downstream feature engineering.

**Parameters**:

| Parameter         | Type                    | Default | Description                                              |
|-------------------|-------------------------|---------|----------------------------------------------------------|
| `df`              | `pd.DataFrame`          | -       | Input DataFrame (typically from `load_data()`).          |
| `id_column`       | `str \| None`           | `None`  | Column to use as row identifier (extracted, not cleaned). |
| `exclude_columns` | `list[str] \| None`     | `None`  | Columns to exclude from processing entirely.             |

**Returns**: A tuple of:
- `pd.DataFrame` - Cleaned DataFrame (without ID or excluded columns).
- `pd.Series | None` - The extracted ID series, or `None` if no `id_column` was specified.

**Key behavior**:
- The input DataFrame is **copied** (`df.copy()`) so the original is never modified.
- The `id_column` is automatically added to the exclude set.
- All excluded columns are dropped before cleaning.

---

## Internal Functions

### `_handle_missing_values(df) -> pd.DataFrame`

Fills `NaN` / `None` values based on column type:

| Column Type | Fill Strategy                                    | Rationale                           |
|-------------|--------------------------------------------------|-------------------------------------|
| Numeric     | Median of the column                             | Robust to outliers (unlike mean).   |
| Non-numeric | Mode (most frequent value), or `"Unknown"` if no mode exists | Preserves the dominant category. |

**Assumption**: Columns with zero missing values are skipped entirely for performance.

### `_coerce_types(df) -> pd.DataFrame`

Applies two type coercion strategies:

1. **Object-to-numeric conversion**: For `object` (string) dtype columns, attempts `pd.to_numeric()`. If more than 90% of values convert successfully, the entire column is cast to numeric and remaining `NaN`s are filled with the column median.

2. **Boolean-like detection**: For `object` columns with exactly 2 unique values, checks if those values are boolean-like (e.g., `"true"/"false"`, `"yes"/"no"`, `"1"/"0"`, `"y"/"n"`). If so, maps them to integer `0`/`1`.

---

## Assumptions and Limitations

1. **Median fill for numerics**: Assumes the median is a reasonable default. For heavily skewed distributions or columns where `NaN` has a semantic meaning (e.g., "not applicable"), this may introduce bias.
2. **Mode fill for categoricals**: If a categorical column has multiple equally common values, the first mode (alphabetically by Pandas behavior) is chosen.
3. **90% threshold for numeric coercion**: If a string column has between 10-90% numeric values, it will remain as `object` type. The threshold is hardcoded.
4. **Boolean detection is case-insensitive**: The check lowercases all values before comparison.
5. **Boolean columns become integer `0`/`1`**: Not Pandas `bool` dtype. This makes them compatible with numerical feature engineering downstream.
6. **No handling of datetime columns**: Date/time strings are not parsed or converted.
7. **Column exclusion is set-based**: If the same column appears in both `id_column` and `exclude_columns`, it is only excluded once (no errors).

---

## Dependencies

- `pandas`
- `numpy`

---

## Usage Example

```python
from outlier_detector.pipeline import load_data, clean_data

df = load_data("data.csv")

# Clean, extracting user_id as the identifier
cleaned_df, ids = clean_data(df, id_column="user_id")

print(cleaned_df.shape)  # Fewer columns (id removed)
print(ids)               # Series of user_id values
```

---

## Data Flow

```
pd.DataFrame (raw from loader)
    |
    v
clean_data(df, id_column="user_id")
    |
    +---> ids: pd.Series (user_id values)
    |
    +---> cleaned_df: pd.DataFrame
              - No ID column
              - No excluded columns
              - Missing values filled
              - Types coerced
              |
              v
          [Next step: engineer_features() in features.py]
```
