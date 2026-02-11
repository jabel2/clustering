# profiler.py - Cluster Profiling and Deviation Analysis

**File**: `src/outlier_detector/clustering/profiler.py`
**Module**: `outlier_detector.clustering`
**Purpose**: Generate human-readable profiles for each cluster and compute how outliers deviate from the norm.

---

## Overview

`profiler.py` serves two critical roles in the outlier detection pipeline:

1. **Cluster profiling**: For each cluster found by HDBSCAN, it describes the dominant characteristics (most common category, median numerical value, distribution statistics). This helps humans understand what "normal" looks like.

2. **Deviation analysis**: For each outlier, it computes specifically _how_ that record differs from the majority cluster. This is essential input for the LLM explanation system.

---

## Data Classes

### `ColumnProfile`

Profile of a single column within a single cluster.

| Field             | Type                 | Description                                                    |
|-------------------|----------------------|----------------------------------------------------------------|
| `name`            | `str`                | Column name.                                                   |
| `dtype`           | `str`                | `"categorical"` or `"numerical"`.                              |
| `mode`            | `Any`                | Most common value (categorical) or median (numerical).         |
| `mode_percentage` | `float`              | Percentage of records in the cluster with the mode value. 0 for numerical columns. |
| `distribution`    | `dict[str, float]`   | For categorical: top-N value percentages. For numerical: `{mean, median, std, min, max}`. |

### `ClusterProfile`

Profile of a single cluster.

| Field        | Type                  | Description                              |
|--------------|-----------------------|------------------------------------------|
| `label`      | `int`                 | Cluster label (-1 for noise).            |
| `size`       | `int`                 | Number of records in this cluster.       |
| `percentage` | `float`               | Percentage of total dataset in this cluster. |
| `columns`    | `list[ColumnProfile]` | Per-column profile within this cluster.  |

### `ProfileResult`

Complete profiling result.

| Field          | Type                   | Description                      |
|----------------|------------------------|----------------------------------|
| `clusters`     | `list[ClusterProfile]` | Profiles for all clusters.       |
| `overall_size` | `int`                  | Total records in the dataset.    |
| `n_clusters`   | `int`                  | Number of clusters (excl. noise).|

---

## Public API

### `ClusterProfiler(categorical_columns, numerical_columns, top_n_categories=5)`

**Constructor Parameters**:

| Parameter              | Type         | Default | Description                                     |
|------------------------|--------------|---------|-------------------------------------------------|
| `categorical_columns`  | `list[str]`  | -       | Categorical column names to profile.            |
| `numerical_columns`    | `list[str]`  | -       | Numerical column names to profile.              |
| `top_n_categories`     | `int`        | `5`     | Number of top category values to include.       |

### `profile(df, cluster_result) -> ProfileResult`

Generates profiles for all clusters.

**Parameters**:

| Parameter        | Type             | Description                                   |
|------------------|------------------|-----------------------------------------------|
| `df`             | `pd.DataFrame`   | Original DataFrame (pre-encoding, post-clean). |
| `cluster_result` | `ClusterResult`  | Clustering result from `HDBSCANClusterer`.    |

**Returns**: `ProfileResult` with a profile for each cluster (including noise/-1).

**Process**:
1. Iterates over each unique cluster label (sorted, so -1/noise comes first).
2. For each cluster, slices the DataFrame to only that cluster's rows.
3. Profiles each categorical and numerical column within that slice.

### `compute_deviation_scores(df, outlier_indices, cluster_result) -> pd.DataFrame`

Computes how each outlier deviates from the majority cluster.

**Parameters**:

| Parameter          | Type             | Description                          |
|--------------------|------------------|--------------------------------------|
| `df`               | `pd.DataFrame`   | Original DataFrame.                  |
| `outlier_indices`  | `np.ndarray`     | Indices of outlier rows.             |
| `cluster_result`   | `ClusterResult`  | Clustering result.                   |

**Returns**: DataFrame with columns `index` and `deviations`, where `deviations` is a dict per outlier.

**Majority cluster identification**:
- Finds the most frequent cluster label (excluding -1) using `pd.Series.mode()`.
- If all points are noise (no valid clusters), falls back to comparing against the entire dataset.

**Deviation types**:

| Column Type  | Deviation Criteria | Reported Data                                                  |
|--------------|-------------------|----------------------------------------------------------------|
| Categorical  | Value differs from majority cluster's mode | `outlier_value`, `majority_value`, `frequency_in_majority` (%) |
| Numerical    | Z-score > 2 (relative to majority cluster) | `outlier_value`, `majority_median`, `z_score`                  |

---

## Internal Functions

### `_profile_categorical(series, name) -> ColumnProfile`

- Computes `value_counts(normalize=True)` on the cluster slice.
- Mode = most frequent value.
- Distribution = top `top_n_categories` values as percentages (rounded to 1 decimal).

### `_profile_numerical(series, name) -> ColumnProfile`

- Computes: mean, median, std, min, max (all rounded to 2 decimals).
- Mode is set to the median.
- `mode_percentage` is 0 (not applicable for continuous values).

---

## Assumptions and Limitations

1. **Majority cluster = most common label**: The deviation analysis compares outliers to the single largest cluster. In datasets with multiple equally-sized clusters, this may not be the most relevant comparison for all outliers.
2. **Z-score threshold of 2**: Only numerical deviations with Z > 2 are reported. Subtler deviations (1 < Z < 2) are not flagged.
3. **Categorical deviation = any difference from mode**: Even if the outlier's value appears in 30% of the majority cluster, it's reported as a deviation. The `frequency_in_majority` field helps gauge severity.
4. **Missing columns are silently skipped**: If a configured column doesn't exist in the DataFrame, no error is raised.
5. **Division by zero**: If `majority_std == 0` for a numerical column (all values identical in the majority cluster), the Z-score computation is skipped for that column.
6. **Uses original (pre-encoded) data**: Profiling operates on human-readable values, not on the one-hot encoded feature matrix. This is intentional for interpretability.

---

## Dependencies

- `numpy`
- `pandas`
- `.clusterer.ClusterResult`

---

## Usage Example

```python
from outlier_detector.clustering import ClusterProfiler

profiler = ClusterProfiler(
    categorical_columns=["department", "location", "job_title"],
    numerical_columns=["tenure_days", "manager_level"],
)

# Profile all clusters
profile_result = profiler.profile(cleaned_df, cluster_result)
for cluster in profile_result.clusters:
    print(f"Cluster {cluster.label}: {cluster.size} records ({cluster.percentage:.1f}%)")
    for col in cluster.columns:
        print(f"  {col.name}: mode={col.mode}, {col.dtype}")

# Compute deviations for outliers
deviation_df = profiler.compute_deviation_scores(cleaned_df, outlier_info.indices, cluster_result)
```

---

## Data Flow

```
pd.DataFrame (cleaned, pre-encoding) + ClusterResult
    |
    v
ClusterProfiler.profile(df, cluster_result)
    |
    v
ProfileResult
    .clusters: [ClusterProfile(-1), ClusterProfile(0), ClusterProfile(1), ...]
    |
    +---> Used for terminal/markdown display
    +---> Used for LLM context building

ClusterProfiler.compute_deviation_scores(df, outlier_indices, cluster_result)
    |
    v
pd.DataFrame with per-outlier deviation dicts
    |
    v
[Next step: ContextBuilder.build() in explanation/context.py]
```
