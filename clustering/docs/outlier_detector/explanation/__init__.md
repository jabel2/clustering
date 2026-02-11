# explanation/__init__.py - Explanation Module Exports

**File**: `src/outlier_detector/explanation/__init__.py`
**Module**: `outlier_detector.explanation`
**Purpose**: Package initializer that re-exports the explanation module's public API.

---

## Overview

This `__init__.py` serves as the public interface for the `explanation` subpackage:

```python
from .context import ContextBuilder
from .agent import ExplanationAgent
```

---

## Exported Symbols (`__all__`)

| Symbol              | Source File   | Type  | Description                                       |
|---------------------|---------------|-------|---------------------------------------------------|
| `ContextBuilder`    | `context.py`  | Class | Builds structured LLM prompts from analysis data. |
| `ExplanationAgent`  | `agent.py`    | Class | Interfaces with Ollama to generate explanations.  |

---

## Usage

```python
from outlier_detector.explanation import ContextBuilder, ExplanationAgent
```

---

## Notes

- The data classes `OutlierContext`, `ExplanationContext`, `OutlierAnalysis`, and `ExplanationResult` are **not** re-exported. They are returned by the public methods but must be imported from their respective modules if type annotations are needed.
