# outlier.py - Outlier Scoring and Extraction

**File**: `src/outlier_detector/clustering/outlier.py`
**Module**: `outlier_detector.clustering`
**Purpose**: Identify, score, and extract outlier records from HDBSCAN clustering results.

---

## Overview

`outlier.py` bridges the gap between raw HDBSCAN clustering output and actionable outlier lists. It combines two signals to identify outliers:
1. **GLOSH outlier scores** from HDBSCAN (continuous 0-1 values).
2. **Noise labels** (cluster label = -1) from HDBSCAN.

The module scores each record, identifies which ones exceed the outlier threshold, sorts them by severity, and provides utilities to extract the original data for those records.

---

## Data Classes

### `OutlierInfo`

Contains all information about detected outliers.

| Field               | Type                | Description                                              |
|---------------------|---------------------|----------------------------------------------------------|
| `indices`           | `np.ndarray`        | Row indices of outlier records in the original DataFrame. Sorted by score (highest first). |
| `scores`            | `np.ndarray`        | GLOSH outlier scores for the outlier records. Sorted descending. |
| `ids`               | `pd.Series \| None` | Identifiers for outlier records (from ID column), or `None`. |
| `total_count`       | `int`               | Total number of records in the dataset.                  |
| `outlier_count`     | `int`               | Number of records classified as outliers.                |
| `outlier_percentage`| `float`             | Percentage of records that are outliers.                 |

---

## Public API

### `OutlierScorer(outlier_threshold=0.8, use_cluster_labels=True)`

**Constructor Parameters**:

| Parameter            | Type    | Default | Description                                                    |
|----------------------|---------|---------|----------------------------------------------------------------|
| `outlier_threshold`  | `float` | `0.8`   | GLOSH score threshold. Points scoring >= this are outliers.    |
| `use_cluster_labels` | `bool`  | `True`  | If `True`, also classify noise points (label=-1) as outliers. |

### `score(cluster_result, ids=None) -> OutlierInfo`

Identifies outliers from clustering results.

**Parameters**:

| Parameter        | Type                | Description                                   |
|------------------|---------------------|-----------------------------------------------|
| `cluster_result` | `ClusterResult`     | Result from `HDBSCANClusterer.fit()`.         |
| `ids`            | `pd.Series \| None` | Optional row identifiers.                     |

**Returns**: `OutlierInfo` with outlier indices, scores, and statistics.

**Outlier detection logic**:
```
is_outlier = (outlier_score >= threshold) OR (label == -1 AND use_cluster_labels)
```

This means a point is an outlier if:
- Its GLOSH score is at or above the threshold, **OR**
- It was assigned to the noise cluster (label -1) and `use_cluster_labels` is `True`.

Results are **sorted by outlier score descending** (most anomalous first).

### `get_outlier_data(df, outlier_info) -> pd.DataFrame`

Extracts the original data rows for all detected outliers.

**Parameters**:

| Parameter      | Type           | Description                        |
|----------------|----------------|------------------------------------|
| `df`           | `pd.DataFrame` | Original cleaned DataFrame.        |
| `outlier_info` | `OutlierInfo`  | Result from `score()`.             |

**Returns**: DataFrame containing only the outlier rows, with an additional `_outlier_score` column appended. Index is reset.

---

## Assumptions and Limitations

1. **Dual-criteria detection**: Using both GLOSH scores AND noise labels means the outlier set is the **union** of both criteria. Some noise points may have low GLOSH scores but are still classified as outliers. Some high-GLOSH points may be in a cluster but are still flagged.
2. **Threshold of 0.8 is aggressive**: The default of 0.8 means only points with very high outlier scores are flagged. Lower thresholds (0.5-0.7) will catch more borderline cases.
3. **Score-based sorting**: Outliers are returned sorted by GLOSH score, not by label or index. The first outlier in the list is always the most anomalous.
4. **ID alignment**: When `ids` are provided, the outlier IDs are extracted using `iloc[outlier_indices]`, which depends on positional alignment between the DataFrame and the clustering result. This works correctly because the pipeline maintains row order.
5. **Division by zero protection**: `outlier_percentage` returns 0 if `total_count` is 0.

---

## Dependencies

- `numpy`
- `pandas`
- `.clusterer.ClusterResult`

---

## Usage Example

```python
from outlier_detector.clustering import HDBSCANClusterer, OutlierScorer

# After clustering
clusterer = HDBSCANClusterer(min_cluster_size=10)
cluster_result = clusterer.fit(features)

# Score outliers
scorer = OutlierScorer(outlier_threshold=0.8)
outlier_info = scorer.score(cluster_result, ids=id_series)

print(f"Found {outlier_info.outlier_count} outliers ({outlier_info.outlier_percentage:.1f}%)")
print(f"Top outlier ID: {outlier_info.ids.iloc[0]}")
print(f"Top outlier score: {outlier_info.scores[0]:.3f}")

# Get the actual data for outliers
outlier_df = scorer.get_outlier_data(cleaned_df, outlier_info)
```

---

## Data Flow

```
ClusterResult (from clusterer.py)
    |
    v
OutlierScorer.score(cluster_result, ids)
    |
    +---> Combine score threshold + noise labels
    +---> Sort by score descending
    +---> Extract IDs
    |
    v
OutlierInfo
    .indices: [42, 7, 103, ...]      (sorted by score)
    .scores:  [0.98, 0.95, 0.91, ...]
    .ids:     ["OUT_3", "OUT_1", ...]
    .outlier_count: 15
    .outlier_percentage: 1.5
    |
    v
[Next: profiler.py for deviation analysis, or explanation module for LLM context]
```
