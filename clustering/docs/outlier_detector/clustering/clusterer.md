# clusterer.py - HDBSCAN Clustering Wrapper

**File**: `src/outlier_detector/clustering/clusterer.py`
**Module**: `outlier_detector.clustering`
**Purpose**: Wrap the HDBSCAN algorithm to perform density-based clustering and provide automatic parameter tuning.

---

## Overview

`clusterer.py` provides the `HDBSCANClusterer` class, which is the core clustering engine of the outlier detection system. HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) is particularly well-suited for outlier detection because:
- It does not require a predefined number of clusters.
- It naturally identifies noise points (label `-1`) as potential outliers.
- It produces outlier scores for every data point.
- It handles clusters of varying densities.

The module also includes an `auto_min_cluster_size()` static method that automatically determines the best `min_cluster_size` parameter using one of three methods.

---

## Data Classes

### `ClusterResult`

Result of a clustering operation.

| Field            | Type          | Description                                                       |
|------------------|---------------|-------------------------------------------------------------------|
| `labels`         | `np.ndarray`  | Cluster label for each sample. `-1` indicates noise/outlier.      |
| `probabilities`  | `np.ndarray`  | Cluster membership probability (0-1) for each sample.             |
| `outlier_scores` | `np.ndarray`  | GLOSH outlier score (0-1) for each sample. Higher = more outlier-like. |
| `n_clusters`     | `int`         | Number of clusters found (excluding noise).                       |
| `n_noise`        | `int`         | Number of noise points (label = -1).                              |

---

## Public API

### `HDBSCANClusterer(min_cluster_size=5, min_samples=None, metric="euclidean", cluster_selection_method="eom")`

**Constructor Parameters**:

| Parameter                  | Type         | Default       | Description                                                                    |
|----------------------------|--------------|---------------|--------------------------------------------------------------------------------|
| `min_cluster_size`         | `int`        | `5`           | Minimum number of points to form a cluster. **Most important parameter.**      |
| `min_samples`              | `int \| None`| `None`        | Minimum samples in neighborhood. If `None`, defaults to `min_cluster_size`.    |
| `metric`                   | `str`        | `"euclidean"` | Distance metric. Passed directly to HDBSCAN.                                  |
| `cluster_selection_method` | `str`        | `"eom"`       | `"eom"` (Excess of Mass) for variable-density clusters; `"leaf"` for more uniform clusters. |

### `fit(features: np.ndarray) -> ClusterResult`

Fits HDBSCAN to a feature matrix and returns clustering results.

**Parameters**:

| Parameter  | Type         | Description                                             |
|------------|--------------|---------------------------------------------------------|
| `features` | `np.ndarray` | Feature matrix of shape `(n_samples, n_features)`.      |

**Returns**: `ClusterResult` with labels, probabilities, outlier scores, and counts.

**Internal details**:
- Sets `gen_min_span_tree=True` to enable the DBCV validity metric.
- Accesses `_clusterer.outlier_scores_` (GLOSH scores) which are computed automatically by HDBSCAN when the minimum spanning tree is generated.

### `clusterer` (property)

Returns the underlying `hdbscan.HDBSCAN` instance after `fit()` has been called, or `None` before.

### `auto_min_cluster_size(features, min_value=3, max_value=None, method="dbcv")` (static method)

Automatically determines the optimal `min_cluster_size` parameter.

**Parameters**:

| Parameter   | Type         | Default  | Description                                           |
|-------------|--------------|----------|-------------------------------------------------------|
| `features`  | `np.ndarray` | -        | Feature matrix.                                       |
| `min_value` | `int`        | `3`      | Minimum candidate value to try.                       |
| `max_value` | `int \| None`| `None`   | Maximum candidate value. Defaults to `min(50, sqrt(n))`. |
| `method`    | `str`        | `"dbcv"` | Selection method: `"dbcv"`, `"heuristic"`, or `"balanced"`. |

**Returns**: `tuple[int, dict]` - The optimal size and a details dictionary with evaluation metrics.

---

## Auto-Tuning Methods

### Method: `"heuristic"`

A simple, fast approach using `log2(n_samples)`.

- **Formula**: `max(min_value, int(log2(n_samples)))`
- **Example**: 1000 samples -> `log2(1000)` = ~10
- **Pros**: Instant, no model fitting required.
- **Cons**: No data-driven optimization.

### Method: `"dbcv"` (default, recommended)

Evaluates all candidate sizes using DBCV (Density-Based Clustering Validation) with penalties.

**Process**:
1. Try each candidate `min_cluster_size` in `[min_value, max_value]`.
2. Fit HDBSCAN and compute `relative_validity_` (DBCV score).
3. Apply three penalties to the raw DBCV score:
   - **Penalty 1 - Insufficient outliers**: If effective outlier percentage < 1%, reduce score by up to 50%. "Effective outliers" = noise points + points in tiny clusters (< `2 * min_cluster_size`).
   - **Penalty 2 - Dominant cluster**: If the largest cluster contains >95% of data, reduce score by up to 30%. This prevents solutions that absorb outliers into the main cluster.
   - **Penalty 3 - Too few clusters**: If only 1 cluster is found, multiply score by 0.5.
4. Select the candidate with the highest adjusted score.

**Output details dict**:
```python
{
    "method": "dbcv",
    "scores": {
        5: {"dbcv": 0.85, "adjusted_score": 0.78, "n_clusters": 3, "noise_pct": 5.2, ...},
        6: {...},
    },
    "best_score": 0.82
}
```

### Method: `"balanced"`

Optimizes for an outlier rate in the 5-15% range.

**Process**:
1. Try each candidate size.
2. Compute noise rate (percentage of points with label `-1`).
3. Score each candidate by how close its noise rate is to the target range midpoint (10%).
4. Require at least 2 clusters.

---

## Assumptions and Limitations

1. **Euclidean distance by default**: Works well for continuous features in comparable scales (which is why RobustScaler is applied upstream). May not be optimal for high-dimensional or mixed-type data.
2. **`min_cluster_size` is the primary tuning knob**: Smaller values find more, smaller clusters; larger values are more conservative.
3. **GLOSH outlier scores**: These are derived from the cluster hierarchy, not from simple distance. A point can have a high outlier score even if it's assigned to a cluster (it's on the cluster periphery).
4. **Auto-tuning searches linearly**: For large datasets with `max_value = 50`, it fits HDBSCAN up to 48 times. This can be slow for large feature matrices.
5. **Exceptions during auto-tuning are silently caught**: If a particular `min_cluster_size` causes HDBSCAN to fail (e.g., all points become noise), it is skipped via `except Exception: continue`.
6. **`gen_min_span_tree=True`**: Required for GLOSH outlier scores and DBCV. Has minor memory/compute overhead.

---

## Dependencies

- `numpy`
- `hdbscan`

---

## Usage Example

```python
from outlier_detector.clustering import HDBSCANClusterer

# Manual parameter
clusterer = HDBSCANClusterer(min_cluster_size=10)
result = clusterer.fit(feature_matrix)

print(f"Clusters: {result.n_clusters}, Noise: {result.n_noise}")
print(f"Outlier scores range: {result.outlier_scores.min():.2f} - {result.outlier_scores.max():.2f}")

# Auto parameter selection
optimal_size, details = HDBSCANClusterer.auto_min_cluster_size(feature_matrix, method="dbcv")
clusterer = HDBSCANClusterer(min_cluster_size=optimal_size)
result = clusterer.fit(feature_matrix)
```

---

## Data Flow

```
np.ndarray (feature matrix from features.py)
    |
    v
HDBSCANClusterer.fit(features)
    |
    +---> hdbscan.HDBSCAN.fit(features)
    |
    +---> Extract labels, probabilities, outlier_scores
    |
    v
ClusterResult
    .labels: [-1, 0, 0, 1, 1, -1, ...]
    .probabilities: [0.0, 0.95, 0.87, ...]
    .outlier_scores: [0.92, 0.12, 0.15, ...]
    .n_clusters: 3
    .n_noise: 15
    |
    v
[Next step: OutlierScorer.score() in outlier.py]
```
