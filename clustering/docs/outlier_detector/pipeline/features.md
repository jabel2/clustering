# features.py - Feature Engineering for Clustering

**File**: `src/outlier_detector/pipeline/features.py`
**Module**: `outlier_detector.pipeline`
**Purpose**: Transform a cleaned DataFrame into a numerical feature matrix suitable for HDBSCAN clustering.

---

## Overview

`features.py` is the final step in the data pipeline before clustering. It takes a cleaned DataFrame and produces a dense NumPy array where:
- Categorical columns are one-hot encoded.
- Numerical columns are scaled using a robust scaler.
- High-cardinality categorical columns are capped to prevent feature explosion.

Column types can be specified manually or auto-detected.

---

## Data Classes

### `FeatureConfig`

Configuration for feature engineering.

| Field                        | Type         | Default | Description                                              |
|------------------------------|--------------|---------|----------------------------------------------------------|
| `categorical_columns`        | `list[str]`  | `[]`    | Explicit list of categorical column names.               |
| `numerical_columns`          | `list[str]`  | `[]`    | Explicit list of numerical column names.                 |
| `high_cardinality_threshold` | `int`        | `20`    | Max unique values before a categorical column is capped. |

### `FeatureResult`

Result of the feature engineering process.

| Field                 | Type          | Description                                              |
|-----------------------|---------------|----------------------------------------------------------|
| `features`            | `np.ndarray`  | Combined feature matrix of shape `(n_samples, n_features)`. |
| `feature_names`       | `list[str]`   | Human-readable names for each feature column.            |
| `categorical_columns` | `list[str]`   | The categorical columns that were used.                  |
| `numerical_columns`   | `list[str]`   | The numerical columns that were used.                    |
| `encoders`            | `dict`        | Dictionary with `"categorical"` (OneHotEncoder) and `"numerical"` (RobustScaler) entries. |

---

## Public API

### `engineer_features(df, config=None) -> FeatureResult`

Transforms a cleaned DataFrame into a feature matrix.

**Parameters**:

| Parameter | Type                     | Default | Description                                          |
|-----------|--------------------------|---------|------------------------------------------------------|
| `df`      | `pd.DataFrame`           | -       | Cleaned DataFrame (output of `clean_data()`).        |
| `config`  | `FeatureConfig \| None`  | `None`  | Feature config. If `None`, auto-detects column types. |

**Returns**: `FeatureResult` with the transformed features and metadata.

**Raises**: `ValueError` if no features are found to process (both categorical and numerical lists are empty after detection).

---

## Internal Functions

### `_detect_column_types(df, config) -> tuple[list[str], list[str]]`

Auto-detects column types when not fully specified in the config.

**Detection logic for unspecified columns**:

| Condition | Classification |
|-----------|---------------|
| Numeric dtype AND unique_ratio < 0.05 AND nunique < 10 | Categorical (low-cardinality numeric) |
| Numeric dtype (all other) | Numerical |
| Non-numeric dtype | Categorical |

- `unique_ratio` = `nunique() / len(df)` - measures what fraction of values are unique.
- If both `categorical_columns` and `numerical_columns` are provided in the config, no detection occurs.
- If only one list is provided, the other is auto-detected from remaining columns.

### `_encode_categorical(df, columns, high_cardinality_threshold) -> tuple[np.ndarray | None, list[str], OneHotEncoder | None]`

One-hot encodes categorical columns.

**Key behaviors**:
1. **High-cardinality capping**: If a column has more than `high_cardinality_threshold` (default 20) unique values, only the top 19 categories are kept. All others are replaced with `"_OTHER_"`.
2. **String conversion**: All categorical values are cast to `str` before encoding for consistent handling.
3. **Unknown handling**: The encoder uses `handle_unknown="ignore"` so unseen categories produce all-zero rows.
4. **Sparse output disabled**: Uses `sparse_output=False` for dense NumPy arrays.

**Output feature names**: Formatted as `{column_name}_{category_value}` (e.g., `department_IT`, `location_New York`).

### `_scale_numerical(df, columns) -> tuple[np.ndarray | None, list[str], RobustScaler | None]`

Scales numerical columns using `sklearn.preprocessing.RobustScaler`.

**Why RobustScaler**: Uses median and IQR instead of mean and standard deviation, making it robust to outliers. This is critical for outlier detection because we don't want outliers to distort the scaling of normal data.

---

## Assumptions and Limitations

1. **Low-cardinality numerics become categorical**: A numeric column with fewer than 10 unique values AND less than 5% unique ratio is treated as categorical. This heuristic may misclassify ordinal scales (e.g., `manager_level` 1-10).
2. **One-hot encoding can produce many features**: A column with 20 unique values generates 20 binary features. With multiple such columns, the feature space can grow rapidly.
3. **High-cardinality threshold is global**: The same threshold (20) applies to all columns. A column with 21 unique values gets capped; one with 19 does not.
4. **No feature interaction terms**: Features are processed independently. Cross-column patterns (e.g., department + title combinations) are not captured.
5. **Missing columns are silently skipped**: If a column name in the config doesn't exist in the DataFrame, it is filtered out without raising an error.
6. **No dimensionality reduction**: No PCA or similar technique is applied. The full one-hot + scaled feature space is passed to HDBSCAN.
7. **RobustScaler uses default quantile range**: 25th to 75th percentile (IQR). Not configurable.

---

## Dependencies

- `numpy`
- `pandas`
- `sklearn.preprocessing.RobustScaler`
- `sklearn.preprocessing.OneHotEncoder`

---

## Usage Example

```python
from outlier_detector.pipeline import load_data, clean_data, engineer_features, FeatureConfig

df = load_data("data.csv")
cleaned_df, ids = clean_data(df, id_column="user_id")

# With explicit column types
config = FeatureConfig(
    categorical_columns=["department", "location", "job_title"],
    numerical_columns=["tenure_days", "manager_level"],
)
result = engineer_features(cleaned_df, config)

print(result.features.shape)       # e.g., (1000, 35)
print(result.feature_names[:5])    # ['department_IT', 'department_HR', ...]

# With auto-detection
result = engineer_features(cleaned_df)
```

---

## Data Flow

```
pd.DataFrame (cleaned)
    |
    v
engineer_features(df, config)
    |
    +---> Auto-detect column types (if needed)
    |
    +---> One-hot encode categoricals
    |         - Cap high-cardinality columns
    |         - Convert to string
    |         - Fit OneHotEncoder
    |
    +---> RobustScale numericals
    |         - Fit RobustScaler
    |
    +---> np.hstack(categorical_features, numerical_features)
    |
    v
FeatureResult
    .features: np.ndarray (n_samples, n_features)
    .feature_names: list[str]
    .encoders: {categorical: OneHotEncoder, numerical: RobustScaler}
    |
    v
[Next step: HDBSCANClusterer.fit() in clusterer.py]
```
