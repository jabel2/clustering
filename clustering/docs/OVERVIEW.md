# Outlier Detector - Comprehensive Documentation

**Version**: 0.1.0
**Location**: `clustering/src/outlier_detector/`
**Entry Point**: `clustering/cli.py`

---

## Table of Contents

1. [What This Tool Does](#what-this-tool-does)
2. [Architecture Overview](#architecture-overview)
3. [Module Breakdown](#module-breakdown)
4. [Complete Data Flow](#complete-data-flow)
5. [CLI Commands Reference](#cli-commands-reference)
6. [Configuration & Parameters](#configuration--parameters)
7. [Input Requirements](#input-requirements)
8. [Output Formats](#output-formats)
9. [External Dependencies](#external-dependencies)
10. [Key Algorithms & Techniques](#key-algorithms--techniques)
11. [Assumptions & Limitations](#assumptions--limitations)
12. [File-by-File Documentation Index](#file-by-file-documentation-index)

---

## What This Tool Does

The Outlier Detector is a **command-line tool** that identifies anomalous records in tabular datasets using density-based clustering (HDBSCAN) and explains the findings using a local LLM (via Ollama). It is designed for scenarios like:

- Detecting unusual accounts in Active Directory groups.
- Finding anomalous entries in HR, finance, or compliance datasets.
- Identifying misconfigured or misplaced records in organizational data.

The tool operates in three modes:

| Command     | Purpose                                                        | Requires LLM? |
|-------------|----------------------------------------------------------------|----------------|
| `analyze`   | Cluster data, identify outliers, display results.              | No             |
| `explain`   | Full analysis + LLM-generated natural-language explanations.   | Yes            |
| `recommend` | LLM recommends optimal settings for a given dataset.           | Yes            |

---

## Architecture Overview

The codebase is organized into four subpackages, each handling a distinct phase of the outlier detection pipeline:

```
src/outlier_detector/
|
+-- __init__.py          # Package root (version only)
+-- cli.py               # CLI commands (analyze, explain, recommend)
+-- config.py            # Configuration dataclasses (reference defaults)
|
+-- pipeline/            # Phase 1: Data Ingestion & Preparation
|   +-- loader.py        #   Load CSV/JSON files
|   +-- cleaner.py       #   Handle missing values, type coercion
|   +-- features.py      #   One-hot encode + scale -> feature matrix
|
+-- clustering/          # Phase 2: Clustering & Outlier Detection
|   +-- clusterer.py     #   HDBSCAN wrapper with auto-tuning
|   +-- outlier.py       #   Score and extract outliers
|   +-- profiler.py      #   Profile clusters, compute deviations
|
+-- explanation/         # Phase 3: LLM Explanation
|   +-- context.py       #   Build structured LLM prompts
|   +-- agent.py         #   Interface with Ollama LLM
|
+-- recommendation/      # Phase 4: LLM-Based Recommendation
    +-- analyzer.py      #   Analyze dataset structure
    +-- recommender.py   #   Get LLM settings recommendations
```

### Design Principles

1. **Pipeline architecture**: Data flows linearly through load -> clean -> feature engineer -> cluster -> score -> profile -> explain.
2. **Separation of concerns**: Each module handles exactly one responsibility. The CLI orchestrates the pipeline.
3. **LLM is optional**: The `analyze` command works entirely without an LLM. Only `explain` and `recommend` require Ollama.
4. **Human-readable outputs**: The tool prioritizes interpretability - cluster profiles use original (pre-encoded) values, and the LLM provides natural-language explanations.

---

## Module Breakdown

### Pipeline Module (`pipeline/`)

Handles all data ingestion and preparation. Three steps transform a raw file into a numerical feature matrix.

| File          | Function             | Input                          | Output                                |
|---------------|----------------------|--------------------------------|---------------------------------------|
| `loader.py`   | `load_data()`       | File path (CSV/JSON)           | Raw `pd.DataFrame`                    |
| `cleaner.py`  | `clean_data()`      | Raw DataFrame + ID column      | Cleaned DataFrame + ID Series         |
| `features.py` | `engineer_features()`| Cleaned DataFrame + config    | `FeatureResult` (NumPy matrix + metadata) |

**Key decisions**:
- Missing numerics are filled with **median** (robust to outliers).
- Missing categoricals are filled with **mode** (or `"Unknown"`).
- Categorical columns with >20 unique values are capped (top 19 + `_OTHER_`).
- Numerical columns are scaled with **RobustScaler** (uses IQR, not std, to resist outlier distortion).
- Boolean-like string columns (`"true"/"false"`, `"yes"/"no"`) are automatically converted to `0`/`1`.

> **Detailed docs**: [loader.md](outlier_detector/pipeline/loader.md) | [cleaner.md](outlier_detector/pipeline/cleaner.md) | [features.md](outlier_detector/pipeline/features.md) | [__init__.md](outlier_detector/pipeline/__init__.md)

---

### Clustering Module (`clustering/`)

Performs the core outlier detection using HDBSCAN and generates interpretable cluster profiles.

| File           | Class                | Purpose                                              |
|----------------|----------------------|------------------------------------------------------|
| `clusterer.py` | `HDBSCANClusterer`   | Fit HDBSCAN, auto-tune `min_cluster_size`.           |
| `outlier.py`   | `OutlierScorer`      | Combine GLOSH scores + noise labels -> outlier list. |
| `profiler.py`  | `ClusterProfiler`    | Describe clusters, compute per-outlier deviations.   |

**Key decisions**:
- **HDBSCAN** chosen over K-means/DBSCAN because it doesn't require a predefined cluster count and handles varying densities.
- Outlier detection uses **dual criteria**: GLOSH score >= threshold (default 0.8) OR noise label (-1).
- **Auto-tuning** searches `min_cluster_size` values from 3 to `min(50, sqrt(n))` and selects the best via DBCV score with penalties for degenerate solutions (too few outliers, dominant clusters, single clusters).
- **Deviation analysis** compares outliers to the **largest cluster** (the "majority"). Categorical deviations report frequency in majority; numerical deviations report z-scores.

> **Detailed docs**: [clusterer.md](outlier_detector/clustering/clusterer.md) | [outlier.md](outlier_detector/clustering/outlier.md) | [profiler.md](outlier_detector/clustering/profiler.md) | [__init__.md](outlier_detector/clustering/__init__.md)

---

### Explanation Module (`explanation/`)

Interfaces with a local Ollama LLM to generate human-readable outlier explanations.

| File          | Class               | Purpose                                              |
|---------------|---------------------|------------------------------------------------------|
| `context.py`  | `ContextBuilder`    | Assemble dataset context, cluster profiles, and outlier details into a structured LLM prompt. |
| `agent.py`    | `ExplanationAgent`  | Send prompt to Ollama, parse response into structured analysis. |

**Key decisions**:
- The LLM prompt includes: dataset context, cluster profiles, per-outlier attribute values, and specific deviations from the majority.
- A **maximum of 25 outliers** are included in the prompt (configurable) to prevent token overflow.
- The LLM is asked to produce **both** free-text explanation AND a structured **JSON block** with per-outlier analysis (risk level, recommended action).
- **Structured analysis parsing** extracts the JSON block using regex. If parsing fails, the free-text explanation is still available.
- The system prompt positions the LLM as _"a data analyst specializing in anomaly detection"_.

> **Detailed docs**: [agent.md](outlier_detector/explanation/agent.md) | [context.md](outlier_detector/explanation/context.md) | [__init__.md](outlier_detector/explanation/__init__.md)

---

### Recommendation Module (`recommendation/`)

Uses an LLM to analyze a dataset's structure and recommend optimal tool settings.

| File              | Class                | Purpose                                           |
|-------------------|----------------------|---------------------------------------------------|
| `analyzer.py`     | `DatasetAnalyzer`    | Profile dataset structure (types, cardinality, distributions, ID candidates). |
| `recommender.py`  | `SettingsRecommender`| Send profile to LLM, parse recommended settings, generate CLI command. |

**Key decisions**:
- **ID column detection** uses both uniqueness ratio (>90%) and name-based heuristics (`id`, `key`, `uuid`, etc.).
- **Type inference** hierarchy: boolean > numerical > text (high cardinality + long strings) > categorical.
- The LLM recommends: column classifications, expected outlier rate, auto-tuning method, column importance weights, and domain-specific outlier signals.
- **Windows text sanitization** replaces Unicode characters that cause encoding errors on Windows consoles.
- A ready-to-use **CLI command** is generated from the recommendations.

> **Detailed docs**: [analyzer.md](outlier_detector/recommendation/analyzer.md) | [recommender.md](outlier_detector/recommendation/recommender.md) | [__init__.md](outlier_detector/recommendation/__init__.md)

---

## Complete Data Flow

### `analyze` Command

```
CSV/JSON file
    |
    v
[1] load_data(file_path)                         # pipeline/loader.py
    |  -> pd.DataFrame (raw)
    v
[2] clean_data(df, id_column)                     # pipeline/cleaner.py
    |  -> (cleaned_df, ids)
    |     - Missing values filled
    |     - Types coerced
    |     - ID column extracted
    v
[3] engineer_features(cleaned_df, config)         # pipeline/features.py
    |  -> FeatureResult
    |     - Categoricals one-hot encoded
    |     - Numericals RobustScaled
    |     - Combined into np.ndarray
    v
[4] HDBSCANClusterer.auto_min_cluster_size()      # clustering/clusterer.py (optional)
    |  -> optimal min_cluster_size
    v
[5] HDBSCANClusterer.fit(features)                # clustering/clusterer.py
    |  -> ClusterResult (labels, probabilities, outlier_scores)
    v
[6] OutlierScorer.score(cluster_result, ids)      # clustering/outlier.py
    |  -> OutlierInfo (indices, scores, ids, counts)
    v
[7] ClusterProfiler.profile(cleaned_df, result)   # clustering/profiler.py
    |  -> ProfileResult (per-cluster column profiles)
    v
[8] Display in terminal / Save to JSON            # cli.py
```

### `explain` Command (extends `analyze`)

```
... steps [1]-[7] same as analyze ...
    v
[8]  OutlierScorer.get_outlier_data()             # clustering/outlier.py
    |   -> outlier_df (original rows for outliers)
    v
[9]  ClusterProfiler.compute_deviation_scores()   # clustering/profiler.py
    |   -> deviation_df (per-outlier, per-column deviations from majority)
    v
[10] ContextBuilder.build()                        # explanation/context.py
    |   -> ExplanationContext (formatted LLM prompt)
    v
[11] ExplanationAgent.explain(context)             # explanation/agent.py
    |   -> ExplanationResult (free-text + structured JSON analysis)
    v
[12] (Optional) DatasetAnalyzer + SettingsRecommender  # recommendation/
    |   -> RecommendationResult
    v
[13] Output: terminal, JSON, Markdown, CSV         # cli.py
```

### `recommend` Command

```
CSV/JSON file
    |
    v
[1] load_data(file_path)                          # pipeline/loader.py
    v
[2] DatasetAnalyzer.analyze(df)                    # recommendation/analyzer.py
    |  -> DatasetProfile (column types, stats, ID candidates)
    v
[3] Display profile in terminal                    # cli.py
    v
[4] SettingsRecommender.recommend(profile, context) # recommendation/recommender.py
    |  -> RecommendationResult (settings + CLI command)
    v
[5] Display recommendations + CLI commands          # cli.py
```

---

## CLI Commands Reference

### Entry Point

```bash
python cli.py <command> [arguments] [options]
```

The root `cli.py` (in the project root) adds `src/` to `sys.path` and delegates to `src/outlier_detector/cli.py`.

### `analyze`

```bash
python cli.py analyze <file_path> \
  [--id-column/-i COLUMN] \
  [--categorical/-c "col1,col2"] \
  [--numerical/-n "col1,col2"] \
  [--min-cluster-size/-m INT] \
  [--auto-cluster-size/-a] \
  [--auto-method METHOD] \
  [--outlier-threshold/-t FLOAT] \
  [--output/-o PATH]
```

### `explain`

```bash
python cli.py explain <file_path> \
  [--id-column/-i COLUMN] \
  [--categorical/-c "col1,col2"] \
  [--numerical/-n "col1,col2"] \
  [--context TEXT] \
  [--min-cluster-size/-m INT] \
  [--auto-cluster-size/-a] \
  [--auto-method METHOD] \
  [--outlier-threshold/-t FLOAT] \
  [--model MODEL_NAME] \
  [--max-outliers-llm INT] \
  [--recommend/-r] \
  [--output-format/-f "json,terminal,markdown,csv"] \
  [--output/-o PATH]
```

### `recommend`

```bash
python cli.py recommend <file_path> \
  [--context TEXT] \
  [--model MODEL_NAME]
```

---

## Configuration & Parameters

### Critical Parameters

| Parameter            | Default  | Impact                                                              |
|----------------------|----------|---------------------------------------------------------------------|
| `min_cluster_size`   | `5`      | **Most important.** Smaller = more clusters, more outliers. Larger = fewer clusters, fewer outliers. Use `--auto-cluster-size` to tune automatically. |
| `outlier_threshold`  | `0.8`    | GLOSH score cutoff. Lower = more outliers flagged. Range: 0-1.      |
| `auto_method`        | `"dbcv"` | `"dbcv"` optimizes cluster quality; `"balanced"` targets 5-15% outlier rate; `"heuristic"` uses log2(n). |

### LLM Parameters

| Parameter          | Default             | Impact                                            |
|--------------------|---------------------|---------------------------------------------------|
| `model`            | `"gpt-oss:20b"`    | Must be available in Ollama. Larger models produce better explanations. |
| `temperature`      | `0.1`               | Very low = deterministic. Higher = more creative.  |
| `max_tokens`       | `4000`              | Maximum LLM response length.                       |
| `max_outliers_llm` | `25`                | Limits prompt size. Increase for comprehensive reports; decrease if LLM struggles with long prompts. |

### Column Configuration

| Option           | Effect                                                                    |
|------------------|---------------------------------------------------------------------------|
| `--id-column`    | Excludes from features, used for labeling outliers.                       |
| `--categorical`  | Forces one-hot encoding. High-cardinality columns are auto-capped at 20.  |
| `--numerical`    | Forces RobustScaler scaling.                                              |
| None specified   | Auto-detection: numeric columns with <10 unique values AND <5% unique ratio become categorical; everything else is inferred. |

---

## Input Requirements

### Supported File Formats

| Format | Requirements                                                            |
|--------|-------------------------------------------------------------------------|
| CSV    | Standard comma-delimited. Headers in first row. UTF-8 compatible.       |
| JSON   | Three layouts: array of objects, `{"data": [...]}`, or single object.   |

### Data Requirements

- **Minimum rows**: HDBSCAN needs at least `min_cluster_size` records (default 5).
- **At least 1 feature**: After cleaning and excluding columns, at least one categorical or numerical column must remain.
- **Mixed types OK**: The pipeline handles datasets with any mix of categorical, numerical, and boolean columns.
- **Missing values OK**: Filled automatically (median for numeric, mode for categorical).
- **No datetime handling**: Date columns are treated as strings (categorical) or text.

---

## Output Formats

### Terminal Output (default for all commands)

- Rich-formatted tables and panels.
- Color-coded status messages.
- Cluster summary table (label, size, percentage).
- Top outliers table (ID, score, first 4 features).
- Markdown-rendered LLM explanation (for `explain`).

### JSON (`explain --output-format json`)

```json
{
  "summary": {
    "total_records": 1000,
    "outlier_count": 15,
    "outlier_percentage": 1.5,
    "n_clusters": 3
  },
  "outliers": [
    {
      "id": "OUT_3",
      "score": 0.98,
      "values": {"department": "Marketing", "tenure_days": "15000"}
    }
  ],
  "explanation": {
    "model": "gpt-oss:20b",
    "content": "## Analysis\n\n### OUT_3..."
  }
}
```

### Markdown (`explain --output-format markdown`)

Complete report with:
- Header with dataset metadata.
- LLM recommendations (if `--recommend`).
- Cluster summary table.
- Detailed cluster profiles (dominant categories, numerical ranges).
- Full LLM explanation.

### CSV (`explain --output-format csv`)

Original dataset with appended columns:
- `_is_outlier` (bool)
- `_outlier_score` (float, 0-1)
- `_why_outlier` (string, from LLM)
- `_unusual_attributes` (string, from LLM)
- `_risk_level` (string: Low/Medium/High)
- `_recommended_action` (string: Review/Flag for removal/Likely legitimate)

---

## External Dependencies

| Package        | Version | Purpose                                              |
|----------------|---------|------------------------------------------------------|
| `typer`        | -       | CLI framework (argument parsing, commands).          |
| `pandas`       | -       | Data manipulation and DataFrame operations.          |
| `numpy`        | -       | Numerical arrays and computations.                   |
| `scikit-learn` | -       | `RobustScaler` and `OneHotEncoder` for features.     |
| `hdbscan`      | -       | HDBSCAN clustering algorithm.                        |
| `ollama`       | -       | Client library for local Ollama LLM server.          |
| `rich`         | -       | Terminal formatting (tables, panels, colors).         |

**Runtime requirement**: An Ollama server running at `localhost:11434` with an appropriate model pulled (only for `explain` and `recommend` commands).

---

## Key Algorithms & Techniques

### HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise)

- **Why**: Automatically determines cluster count, handles varying cluster densities, naturally identifies noise/outliers.
- **Key parameter**: `min_cluster_size` - the smallest group the algorithm considers a real cluster.
- **Output**: Cluster labels (noise = -1), membership probabilities, GLOSH outlier scores.

### GLOSH (Global-Local Outlier Scores from Hierarchies)

- Derived from the HDBSCAN cluster hierarchy.
- Score range: 0 (very inlier-like) to 1 (very outlier-like).
- Considers both local density and global structure.

### RobustScaler

- Scales features using median and IQR (interquartile range) instead of mean and standard deviation.
- **Why**: Prevents outliers from distorting the scaling of normal data. Critical because the tool's purpose is to detect outliers.

### One-Hot Encoding

- Converts categorical values to binary feature columns.
- High-cardinality columns (>20 unique values) are capped: top 19 values + `_OTHER_`.

### DBCV (Density-Based Clustering Validation)

- Used in `auto_min_cluster_size(method="dbcv")` to evaluate cluster quality.
- Higher scores indicate better-separated clusters.
- The implementation adds penalties for degenerate solutions (too few outliers, single dominant cluster).

---

## Assumptions & Limitations

### Data Assumptions

1. Data is tabular (rows = records, columns = attributes).
2. Records are independent (no time-series or sequence dependencies).
3. Outliers are a small minority of the dataset.
4. CSV files use comma delimiters and UTF-8 encoding.
5. Column names do not contain commas (CLI uses comma-separated lists).

### Algorithmic Assumptions

1. Euclidean distance is meaningful for the feature space (after encoding/scaling).
2. Normal records form dense clusters; outliers are in sparse regions.
3. The largest cluster represents the "majority" behavior (used for deviation analysis).
4. Z-score > 2 indicates a meaningful numerical deviation.
5. One-hot encoding is appropriate for categorical features (vs. target encoding, embeddings, etc.).

### Infrastructure Assumptions

1. Ollama is running locally at `localhost:11434` (for `explain` and `recommend`).
2. The specified model is already pulled in Ollama.
3. The LLM can handle prompts of 5,000-10,000+ characters.
4. The LLM will comply with JSON formatting instructions in the prompt.

### Known Limitations

1. **No datetime handling**: Date/time columns are treated as categorical strings.
2. **No feature interaction terms**: Cross-column patterns are not captured.
3. **No dimensionality reduction**: High-dimensional feature spaces are passed directly to HDBSCAN.
4. **Single majority comparison**: Deviations are computed against the largest cluster only, which may miss outliers relative to other clusters.
5. **No streaming**: Entire dataset is loaded into memory.
6. **No config file support**: All configuration is via CLI options.
7. **LLM output quality varies**: Structured analysis parsing depends on model compliance.
8. **`column_weights` from recommendations are advisory only**: The pipeline doesn't apply them.
9. **Windows-specific text sanitization**: The Unicode sanitization in `recommender.py` is tailored for Windows.

---

## File-by-File Documentation Index

Each file in `src/` has a detailed documentation file in `docs/`:

### Top Level
| Source File | Documentation |
|-------------|---------------|
| `src/outlier_detector/__init__.py` | [__init__.md](outlier_detector/__init__.md) |
| `src/outlier_detector/cli.py` | [cli.md](outlier_detector/cli.md) |
| `src/outlier_detector/config.py` | [config.md](outlier_detector/config.md) |

### Pipeline Module
| Source File | Documentation |
|-------------|---------------|
| `src/outlier_detector/pipeline/__init__.py` | [pipeline/__init__.md](outlier_detector/pipeline/__init__.md) |
| `src/outlier_detector/pipeline/loader.py` | [pipeline/loader.md](outlier_detector/pipeline/loader.md) |
| `src/outlier_detector/pipeline/cleaner.py` | [pipeline/cleaner.md](outlier_detector/pipeline/cleaner.md) |
| `src/outlier_detector/pipeline/features.py` | [pipeline/features.md](outlier_detector/pipeline/features.md) |

### Clustering Module
| Source File | Documentation |
|-------------|---------------|
| `src/outlier_detector/clustering/__init__.py` | [clustering/__init__.md](outlier_detector/clustering/__init__.md) |
| `src/outlier_detector/clustering/clusterer.py` | [clustering/clusterer.md](outlier_detector/clustering/clusterer.md) |
| `src/outlier_detector/clustering/outlier.py` | [clustering/outlier.md](outlier_detector/clustering/outlier.md) |
| `src/outlier_detector/clustering/profiler.py` | [clustering/profiler.md](outlier_detector/clustering/profiler.md) |

### Explanation Module
| Source File | Documentation |
|-------------|---------------|
| `src/outlier_detector/explanation/__init__.py` | [explanation/__init__.md](outlier_detector/explanation/__init__.md) |
| `src/outlier_detector/explanation/agent.py` | [explanation/agent.md](outlier_detector/explanation/agent.md) |
| `src/outlier_detector/explanation/context.py` | [explanation/context.md](outlier_detector/explanation/context.md) |

### Recommendation Module
| Source File | Documentation |
|-------------|---------------|
| `src/outlier_detector/recommendation/__init__.py` | [recommendation/__init__.md](outlier_detector/recommendation/__init__.md) |
| `src/outlier_detector/recommendation/analyzer.py` | [recommendation/analyzer.md](outlier_detector/recommendation/analyzer.md) |
| `src/outlier_detector/recommendation/recommender.py` | [recommendation/recommender.md](outlier_detector/recommendation/recommender.md) |
