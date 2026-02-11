# analyzer.py - Dataset Structure Analyzer

**File**: `src/outlier_detector/recommendation/analyzer.py`
**Module**: `outlier_detector.recommendation`
**Purpose**: Analyze a dataset's structure (column types, distributions, uniqueness) to produce a profile that helps an LLM recommend optimal outlier detection settings.

---

## Overview

`analyzer.py` examines a raw DataFrame and produces a structured `DatasetProfile`. This profile captures:
- Per-column metadata (type, cardinality, nulls, sample values, statistics).
- ID column candidates (columns likely to be unique identifiers).
- Sample rows for the LLM to understand the data shape.

The analyzer does **not** perform any clustering or outlier detection. Its sole purpose is to describe the dataset so the LLM can make informed recommendations about how to configure the pipeline.

---

## Data Classes

### `ColumnInfo`

Information about a single column.

| Field          | Type                   | Description                                              |
|----------------|------------------------|----------------------------------------------------------|
| `name`         | `str`                  | Column name.                                             |
| `dtype`        | `str`                  | Inferred semantic type: `"categorical"`, `"numerical"`, `"boolean"`, or `"text"`. |
| `unique_count` | `int`                  | Number of unique values.                                 |
| `null_count`   | `int`                  | Number of null/NaN values.                               |
| `null_pct`     | `float`                | Percentage of null values.                               |
| `sample_values`| `list[str]`            | Up to 5 sample non-null values (as strings).             |
| `min_val`      | `float \| None`        | Minimum value (numerical only).                          |
| `max_val`      | `float \| None`        | Maximum value (numerical only).                          |
| `mean_val`     | `float \| None`        | Mean value (numerical only).                             |
| `median_val`   | `float \| None`        | Median value (numerical only).                           |
| `std_val`      | `float \| None`        | Standard deviation (numerical only).                     |
| `top_values`   | `dict[str, float]`     | Top-5 category values with percentages (categorical only). |

### `DatasetProfile`

Complete profile of a dataset.

| Field                  | Type               | Description                                |
|------------------------|--------------------|--------------------------------------------|
| `n_rows`               | `int`              | Number of rows.                            |
| `n_columns`            | `int`              | Number of columns.                         |
| `columns`              | `list[ColumnInfo]`  | Per-column info.                           |
| `sample_rows`          | `list[dict]`        | Up to 3 sample rows (values as strings).   |
| `id_column_candidates` | `list[str]`         | Column names likely to be IDs.             |

---

## Public API

### `DatasetAnalyzer(max_sample_values=5, max_sample_rows=3, max_top_values=5)`

**Constructor Parameters**:

| Parameter           | Type  | Default | Description                              |
|---------------------|-------|---------|------------------------------------------|
| `max_sample_values` | `int` | `5`     | Max sample values to include per column. |
| `max_sample_rows`   | `int` | `3`     | Max sample rows to include.              |
| `max_top_values`    | `int` | `5`     | Max top categorical values to include.   |

### `analyze(df) -> DatasetProfile`

Analyzes a DataFrame and returns its profile.

**Parameters**:

| Parameter | Type           | Description            |
|-----------|----------------|------------------------|
| `df`      | `pd.DataFrame` | DataFrame to analyze.  |

**Returns**: `DatasetProfile` with complete column information and samples.

### `to_prompt_text(profile) -> str`

Converts a `DatasetProfile` to formatted text suitable for inclusion in an LLM prompt.

**Output format**:
```
Dataset: 1000 rows, 9 columns

## Columns
- **user_id** (categorical) - 1000 unique values
  Examples: 'U1000', 'U1001', 'U1002'
- **tenure_days** (numerical) - 850 unique values
  Range: [1.00, 5000.00], Mean: 1200.50, Std: 400.00
- **department** (categorical) - 5 unique values
  Top values: 'IT': 25.0%, 'Sales': 22.0%, 'HR': 18.0%

Likely ID columns: user_id

## Sample Rows
1. user_id=U1000, department=IT, job_title=DevOps Engineer, ...
2. user_id=U1001, department=Sales, ...
```

---

## Internal Functions

### `_analyze_column(df, col) -> ColumnInfo`

Performs detailed analysis of a single column:
1. Counts unique values and nulls.
2. Infers semantic type via `_infer_dtype()`.
3. Extracts sample values.
4. Adds type-specific statistics (numerical stats or categorical top values).

### `_infer_dtype(series, unique_count, n_rows) -> str`

Infers the semantic type of a column using the following hierarchy:

| Priority | Check                                    | Result          |
|----------|------------------------------------------|-----------------|
| 1        | Unique values are a subset of `{0, 1, True, False, "0", "1", "true", "false", "True", "False"}` | `"boolean"` |
| 2        | Pandas numeric dtype                      | `"numerical"`   |
| 3        | >50% unique AND average string length > 50 | `"text"`       |
| 4        | Everything else                           | `"categorical"` |

### `_find_id_candidates(df, columns) -> list[str]`

Identifies columns likely to be unique identifiers:

| Condition                                  | Qualifies as ID candidate? |
|--------------------------------------------|---------------------------|
| Uniqueness > 90% (`nunique / len(df)`)     | Yes                       |
| Name contains `id`, `key`, `uuid`, `guid`, `identifier`, or `code` AND uniqueness > 50% | Yes |

---

## Assumptions and Limitations

1. **Type inference is heuristic**: The boolean check uses a fixed set of known boolean values. Custom boolean representations (e.g., `"active"/"inactive"`) won't be detected.
2. **Text detection threshold**: A column needs >50% unique values AND average length >50 characters to be classified as `"text"`. Short free-text fields may be misclassified as categorical.
3. **Sample values are from `head()`**: The first N rows may not be representative of the full dataset. No random sampling is performed.
4. **ID detection by name**: The substring check is case-insensitive and may match unintended columns (e.g., a column named `"acid_level"` contains `"id"`).
5. **No datetime detection**: Date/time columns are classified as either `"categorical"` or `"text"` depending on cardinality and string length.
6. **Statistics are computed on non-null values only**: If a numerical column has many nulls, the statistics reflect only the present values.
7. **Prompt text limits sample rows to 6 columns**: `to_prompt_text()` only shows the first 6 columns per sample row to keep the text compact.

---

## Dependencies

- `pandas`
- `numpy`

---

## Usage Example

```python
from outlier_detector.recommendation import DatasetAnalyzer

analyzer = DatasetAnalyzer()
profile = analyzer.analyze(df)

print(f"Rows: {profile.n_rows}, Columns: {profile.n_columns}")
print(f"ID candidates: {profile.id_column_candidates}")

for col in profile.columns:
    print(f"  {col.name}: {col.dtype}, {col.unique_count} unique, {col.null_pct:.1f}% null")

# Convert to LLM-ready text
prompt_text = analyzer.to_prompt_text(profile)
```

---

## Data Flow

```
pd.DataFrame (raw, as loaded)
    |
    v
DatasetAnalyzer.analyze(df)
    |
    +---> Per-column analysis (_analyze_column)
    |         - Type inference
    |         - Statistics/distributions
    |
    +---> ID candidate detection
    +---> Sample row extraction
    |
    v
DatasetProfile
    .columns: [ColumnInfo(...), ...]
    .id_column_candidates: ["user_id"]
    .sample_rows: [{...}, ...]
    |
    v
[Next step: SettingsRecommender.recommend() in recommender.py]
```
