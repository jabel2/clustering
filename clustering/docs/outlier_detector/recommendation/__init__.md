# recommendation/__init__.py - Recommendation Module Exports

**File**: `src/outlier_detector/recommendation/__init__.py`
**Module**: `outlier_detector.recommendation`
**Purpose**: Package initializer that re-exports the recommendation module's public API.

---

## Overview

This `__init__.py` serves as the public interface for the `recommendation` subpackage:

```python
from .analyzer import DatasetAnalyzer
from .recommender import SettingsRecommender
```

---

## Exported Symbols (`__all__`)

| Symbol               | Source File      | Type  | Description                                       |
|----------------------|------------------|-------|---------------------------------------------------|
| `DatasetAnalyzer`    | `analyzer.py`    | Class | Analyzes dataset structure for LLM consumption.   |
| `SettingsRecommender`| `recommender.py` | Class | Gets LLM recommendations for pipeline settings.   |

---

## Usage

```python
from outlier_detector.recommendation import DatasetAnalyzer, SettingsRecommender
```
