# config.py - Configuration Data Classes

**File**: `src/outlier_detector/config.py`
**Module**: `outlier_detector.config`
**Purpose**: Define centralized configuration data classes for all components of the outlier detection system.

---

## Overview

`config.py` provides a set of `@dataclass` configuration objects that group all tunable parameters for the system's components. These serve as the canonical reference for default values and parameter documentation.

**Important note**: While this file defines a comprehensive configuration system, the CLI module (`cli.py`) currently constructs component instances directly with parameters from command-line options rather than building `Config` objects. The data classes here serve as a design reference and could be used for future configuration-file-based workflows.

---

## Data Classes

### `ClusteringConfig`

Configuration for HDBSCAN clustering.

| Field                      | Type          | Default       | Description                                            |
|----------------------------|---------------|---------------|--------------------------------------------------------|
| `min_cluster_size`         | `int`         | `5`           | Minimum points to form a cluster.                      |
| `min_samples`              | `Optional[int]` | `None`      | Minimum samples in neighborhood (defaults to min_cluster_size). |
| `metric`                   | `str`         | `"euclidean"` | Distance metric.                                       |
| `cluster_selection_method` | `str`         | `"eom"`       | `"eom"` (Excess of Mass) or `"leaf"`.                 |

### `OutlierConfig`

Configuration for outlier detection thresholds.

| Field               | Type    | Default | Description                                              |
|---------------------|---------|---------|----------------------------------------------------------|
| `outlier_threshold` | `float` | `0.8`   | GLOSH score threshold; points >= this are outliers.      |
| `use_cluster_labels`| `bool`  | `True`  | Also treat cluster=-1 (noise) as outliers.               |

### `LLMConfig`

Configuration for LLM (Ollama) explanations.

| Field         | Type    | Default                    | Description                          |
|---------------|---------|----------------------------|--------------------------------------|
| `model`       | `str`   | `"llama3.1:8b"`           | Ollama model name.                   |
| `host`        | `str`   | `"http://localhost:11434"` | Ollama server URL.                   |
| `temperature` | `float` | `0.3`                      | Sampling temperature.                |
| `max_tokens`  | `int`   | `2000`                     | Maximum response tokens.             |

**Note**: The default model here (`"llama3.1:8b"`) differs from the CLI default (`"gpt-oss:20b"`). The CLI overrides these defaults via command-line options.

### `FeatureConfig` (duplicate definition)

Configuration for feature engineering.

| Field                        | Type              | Default | Description                                              |
|------------------------------|-------------------|---------|----------------------------------------------------------|
| `categorical_columns`        | `list[str]`       | `[]`    | Explicit categorical column names.                       |
| `numerical_columns`          | `list[str]`       | `[]`    | Explicit numerical column names.                         |
| `id_column`                  | `Optional[str]`   | `None`  | ID column name.                                          |
| `exclude_columns`            | `list[str]`       | `[]`    | Columns to exclude from processing.                      |
| `high_cardinality_threshold` | `int`             | `20`    | Max unique values before categorical capping.            |

**Note**: This `FeatureConfig` has additional fields (`id_column`, `exclude_columns`) compared to the one in `features.py`. The CLI and pipeline use the `FeatureConfig` from `features.py`, not this one.

### `Config`

Main configuration container that composes all sub-configs.

| Field       | Type               | Default                    | Description                   |
|-------------|--------------------|----------------------------|-------------------------------|
| `clustering`| `ClusteringConfig` | `ClusteringConfig()`       | Clustering parameters.        |
| `outlier`   | `OutlierConfig`    | `OutlierConfig()`          | Outlier threshold parameters. |
| `llm`       | `LLMConfig`        | `LLMConfig()`              | LLM connection parameters.    |
| `features`  | `FeatureConfig`    | `FeatureConfig()`          | Feature engineering parameters.|

---

## Assumptions and Limitations

1. **Not actively used by the CLI**: The `Config` composite class is defined but not instantiated by any command. The CLI passes parameters directly.
2. **Duplicate `FeatureConfig`**: There are two `FeatureConfig` definitions - one here and one in `pipeline/features.py`. The pipeline uses the one from `features.py`.
3. **`LLMConfig` defaults differ from CLI**: `config.py` defaults to `llama3.1:8b` with `temperature=0.3` and `max_tokens=2000`; the CLI defaults to `gpt-oss:20b` with `temperature=0.1` and `max_tokens=4000`.
4. **No config file loading**: There is no mechanism to load configuration from YAML/TOML/JSON files. All configuration comes from CLI options.

---

## Dependencies

- `dataclasses` (stdlib)
- `typing.Optional` (stdlib)

---

## Usage Example

```python
from outlier_detector.config import Config, ClusteringConfig

# Create default config
config = Config()

# Create with custom clustering
config = Config(
    clustering=ClusteringConfig(min_cluster_size=10, metric="manhattan"),
)

print(config.clustering.min_cluster_size)  # 10
print(config.llm.model)  # "llama3.1:8b"
```
