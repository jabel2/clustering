# pipeline/__init__.py - Pipeline Module Exports

**File**: `src/outlier_detector/pipeline/__init__.py`
**Module**: `outlier_detector.pipeline`
**Purpose**: Package initializer that re-exports the pipeline's public API.

---

## Overview

This `__init__.py` serves as the public interface for the `pipeline` subpackage. It imports and re-exports the four key symbols that other modules need:

```python
from .loader import load_data
from .cleaner import clean_data
from .features import engineer_features, FeatureConfig
```

---

## Exported Symbols (`__all__`)

| Symbol              | Source File   | Type      | Description                                   |
|---------------------|---------------|-----------|-----------------------------------------------|
| `load_data`         | `loader.py`   | Function  | Load CSV/JSON files into DataFrames.          |
| `clean_data`        | `cleaner.py`  | Function  | Clean data (missing values, type coercion).   |
| `engineer_features` | `features.py` | Function  | Transform DataFrame to feature matrix.        |
| `FeatureConfig`     | `features.py` | Dataclass | Configuration for feature engineering.        |

---

## Usage

```python
# Preferred: import from the package level
from outlier_detector.pipeline import load_data, clean_data, engineer_features, FeatureConfig

# Also valid: import from individual modules
from outlier_detector.pipeline.loader import load_data
```

---

## Notes

- The `FeatureResult` dataclass from `features.py` is **not** re-exported at the package level. It is returned by `engineer_features()` but must be imported directly if needed as a type annotation.
