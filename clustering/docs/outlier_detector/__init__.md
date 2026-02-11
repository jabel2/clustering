# outlier_detector/__init__.py - Package Root

**File**: `src/outlier_detector/__init__.py`
**Module**: `outlier_detector`
**Purpose**: Top-level package initializer for the outlier detection tool.

---

## Overview

This is the root `__init__.py` for the `outlier_detector` package. It sets the package version and provides the module docstring.

```python
"""Outlier detection CLI tool with clustering and LLM explanations."""

__version__ = "0.1.0"
```

---

## Details

| Field         | Value                                                        |
|---------------|--------------------------------------------------------------|
| `__version__` | `"0.1.0"` - The package is in early development.            |
| Docstring     | "Outlier detection CLI tool with clustering and LLM explanations." |

---

## Notes

- This file does **not** re-export any symbols from submodules. All imports must go through the subpackages:
  - `outlier_detector.pipeline`
  - `outlier_detector.clustering`
  - `outlier_detector.explanation`
  - `outlier_detector.recommendation`
- The `__version__` is not referenced anywhere else in the codebase currently.
