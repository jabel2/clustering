# clustering/__init__.py - Clustering Module Exports

**File**: `src/outlier_detector/clustering/__init__.py`
**Module**: `outlier_detector.clustering`
**Purpose**: Package initializer that re-exports the clustering module's public API.

---

## Overview

This `__init__.py` serves as the public interface for the `clustering` subpackage. It imports and re-exports the three main classes:

```python
from .clusterer import HDBSCANClusterer
from .outlier import OutlierScorer
from .profiler import ClusterProfiler
```

---

## Exported Symbols (`__all__`)

| Symbol              | Source File     | Type  | Description                                    |
|---------------------|-----------------|-------|------------------------------------------------|
| `HDBSCANClusterer`  | `clusterer.py`  | Class | HDBSCAN clustering with auto-tuning support.   |
| `OutlierScorer`     | `outlier.py`    | Class | Score and extract outliers from cluster results.|
| `ClusterProfiler`   | `profiler.py`   | Class | Profile clusters and compute deviations.        |

---

## Usage

```python
from outlier_detector.clustering import HDBSCANClusterer, OutlierScorer, ClusterProfiler
```

---

## Notes

- The data classes `ClusterResult`, `OutlierInfo`, `ColumnProfile`, `ClusterProfile`, and `ProfileResult` are **not** re-exported at the package level. They are returned by the public methods but must be imported from their respective modules if needed as type annotations.
