# cli.py - CLI Interface (Inner)

**File**: `src/outlier_detector/cli.py`
**Module**: `outlier_detector.cli`
**Purpose**: Define the Typer-based CLI commands for the outlier detection tool: `analyze`, `explain`, and `recommend`.

---

## Overview

This is the main CLI module containing all three user-facing commands. It orchestrates the entire pipeline from data loading through clustering, profiling, LLM explanation, and output generation. Each command is a self-contained workflow that composes the pipeline, clustering, explanation, and recommendation modules.

The CLI uses:
- **Typer** for argument/option parsing and command routing.
- **Rich** for colorized terminal output, tables, panels, and Markdown rendering.

---

## Commands

### `analyze` - Basic Outlier Detection

**Usage**:
```bash
python cli.py analyze <file_path> [options]
```

**Purpose**: Run HDBSCAN clustering on a dataset and identify outliers. Displays results in the terminal and optionally saves to JSON.

**Arguments & Options**:

| Argument/Option        | Short | Type    | Default | Description                                              |
|------------------------|-------|---------|---------|----------------------------------------------------------|
| `file_path`            | -     | `Path`  | Required| Path to CSV or JSON data file.                           |
| `--id-column`          | `-i`  | `str`   | `None`  | Column to use as row identifier.                         |
| `--categorical`        | `-c`  | `str`   | `None`  | Comma-separated categorical column names.                |
| `--numerical`          | `-n`  | `str`   | `None`  | Comma-separated numerical column names.                  |
| `--min-cluster-size`   | `-m`  | `int`   | `5`     | Minimum cluster size for HDBSCAN (ignored if `--auto-cluster-size`). |
| `--auto-cluster-size`  | `-a`  | `bool`  | `False` | Automatically determine optimal min_cluster_size.        |
| `--auto-method`        | -     | `str`   | `"dbcv"`| Method for auto size: `dbcv`, `balanced`, `heuristic`.   |
| `--outlier-threshold`  | `-t`  | `float` | `0.8`   | Outlier score threshold (0-1).                           |
| `--output`             | `-o`  | `Path`  | `None`  | Output JSON file path.                                   |

**Pipeline flow**:
1. `load_data()` -> Load CSV/JSON
2. `clean_data()` -> Handle missing values, extract ID
3. `engineer_features()` -> One-hot encode + scale
4. `HDBSCANClusterer.auto_min_cluster_size()` (if `--auto-cluster-size`)
5. `HDBSCANClusterer.fit()` -> Cluster
6. `OutlierScorer.score()` -> Identify outliers
7. `ClusterProfiler.profile()` -> Profile clusters
8. Display results in terminal (tables)
9. Optionally save to JSON

**Terminal output**: Shows a cluster summary table and a top outliers table with IDs, scores, and the first 4 feature values.

---

### `explain` - Outlier Detection + LLM Explanation

**Usage**:
```bash
python cli.py explain <file_path> [options]
```

**Purpose**: Run the full analysis pipeline PLUS generate LLM-powered natural-language explanations for each outlier. Supports multiple output formats.

**Additional options beyond `analyze`**:

| Option               | Short | Type    | Default                           | Description                                    |
|----------------------|-------|---------|-----------------------------------|------------------------------------------------|
| `--context`          | -     | `str`   | `""`                              | Dataset description for LLM context.           |
| `--model`            | -     | `str`   | `"gpt-oss:20b"`                  | Ollama model to use.                           |
| `--max-outliers-llm` | -     | `int`   | `25`                              | Max outliers to send to LLM.                   |
| `--recommend`        | `-r`  | `bool`  | `False`                           | Include LLM recommendations in the report.     |
| `--output-format`    | `-f`  | `str`   | `"json,terminal,markdown,csv"`   | Comma-separated output formats.                |
| `--output`           | `-o`  | `Path`  | `None`                            | Base output path (extensions added automatically). |

**Additional pipeline steps** (beyond `analyze`):
1. `OutlierScorer.get_outlier_data()` -> Get outlier rows
2. `ClusterProfiler.compute_deviation_scores()` -> Compute deviations
3. `ContextBuilder.build()` -> Build LLM prompt
4. `ExplanationAgent.check_connection()` -> Verify Ollama
5. `ExplanationAgent.explain()` -> Get LLM explanation
6. (Optional) `DatasetAnalyzer.analyze()` + `SettingsRecommender.recommend()` -> Get recommendations

**Output formats**:

| Format     | Extension | Description                                            |
|------------|-----------|--------------------------------------------------------|
| `terminal` | -         | Rich panel with Markdown-rendered explanation.         |
| `json`     | `.json`   | Full results with outliers, scores, and explanation.   |
| `markdown` | `.md`     | Report with cluster summary, profiles, and explanation.|
| `csv`      | `.csv`    | Original data with analysis columns appended.          |

**CSV output columns** (appended to original data):
- `_is_outlier` (bool)
- `_outlier_score` (float)
- `_why_outlier` (str, from LLM structured analysis)
- `_unusual_attributes` (str, from LLM)
- `_risk_level` (str, from LLM)
- `_recommended_action` (str, from LLM)

**Early exit**: If no outliers are detected, prints a success message and exits with code 0.

---

### `recommend` - LLM-Based Settings Recommendation

**Usage**:
```bash
python cli.py recommend <file_path> [options]
```

**Purpose**: Analyze a dataset's structure and use an LLM to recommend optimal outlier detection settings, then output a ready-to-use CLI command.

**Arguments & Options**:

| Argument/Option | Short | Type   | Default         | Description                                      |
|-----------------|-------|--------|-----------------|--------------------------------------------------|
| `file_path`     | -     | `Path` | Required        | Path to CSV or JSON data file.                   |
| `--context`     | -     | `str`  | `""`            | Domain context description.                      |
| `--model`       | -     | `str`  | `"gpt-oss:20b"` | Ollama model to use.                             |

**Pipeline flow**:
1. `load_data()` -> Load data
2. `DatasetAnalyzer.analyze()` -> Profile dataset
3. Display dataset profile in terminal
4. `SettingsRecommender.recommend()` -> Get LLM recommendations
5. Display recommendations and generated CLI commands

**Terminal output**: Shows the dataset profile (columns with types and stats), LLM recommendations (ID column, categorical/numerical classifications, outlier signals, reasoning), and two suggested CLI commands (one for `analyze`, one for `explain`).

---

## Private Helper Functions

### `_display_results(outlier_info, profile_result, df, scorer, cluster_result, ids)`

Renders the analysis summary and tables in the terminal using Rich.

### `_save_results(output_path, outlier_info, profile_result, df, scorer, ids)`

Saves analysis results to JSON with structure:
```json
{
  "summary": {"total_records": ..., "outlier_count": ..., ...},
  "clusters": [...],
  "outliers": [{"id": ..., "score": ..., "values": {...}}]
}
```

### `_save_explanation_json(output_path, outlier_info, profile_result, explanation_result, df, scorer, ids)`

Saves explanation results to JSON, including the LLM explanation text and model info.

### `_save_explanation_markdown(output_path, context, outlier_info, profile_result, explanation_result, recommendation_result=None)`

Generates a complete Markdown report with:
- Header with dataset metadata.
- LLM recommendations section (if available).
- Cluster summary table.
- Detailed cluster profiles (categorical dominant values, numerical ranges).
- LLM explanation text.

### `_save_annotated_csv(output_path, original_df, outlier_info, explanation_result)`

Creates an annotated CSV by:
1. Copying the original DataFrame.
2. Adding `_is_outlier`, `_outlier_score`, `_why_outlier`, `_unusual_attributes`, `_risk_level`, `_recommended_action` columns.
3. Filling in values for outlier rows from the LLM's structured analysis.
4. Matching outliers to rows by ID.

---

## Assumptions and Limitations

1. **Default output path**: If no `--output` is specified for `explain`, the base path is `{input_file_stem}_analysis` (e.g., `test_data_analysis.json`).
2. **All output formats enabled by default**: The `explain` command produces JSON, terminal, Markdown, and CSV by default. Users must explicitly limit with `--output-format`.
3. **Comma-separated column lists**: Column names cannot contain commas because the `--categorical` and `--numerical` options split on commas.
4. **Error handling**: `FileNotFoundError` and `ValueError` during loading result in a clean error message and `typer.Exit(1)`. Connection errors to Ollama also produce clean messages.
5. **Top outliers table shows first 4 feature columns**: Hard-coded limit for readability. Wide datasets only show a subset.
6. **CSV annotation depends on LLM compliance**: The `_why_outlier`, `_unusual_attributes`, etc. fields are only populated if the LLM produced a valid JSON block. Otherwise, they remain empty strings.
7. **Recommendation in `explain` is optional**: Must be explicitly enabled with `--recommend`/`-r`.

---

## Dependencies

- `json` (stdlib)
- `pathlib.Path` (stdlib)
- `typing.Optional` (stdlib)
- `typer`
- `rich` (Console, Table, Panel, Markdown)
- All four subpackages: `pipeline`, `clustering`, `explanation`, `recommendation`

---

## Usage Examples

```bash
# Basic analysis
python cli.py analyze data.csv --id-column user_id

# Analysis with auto-tuning and explicit column types
python cli.py analyze data.csv \
  --id-column user_id \
  --categorical "department,location" \
  --numerical "tenure_days,manager_level" \
  --auto-cluster-size \
  --auto-method balanced

# Full explanation with LLM
python cli.py explain data.csv \
  --id-column user_id \
  --auto-cluster-size \
  --context "AD group: Finance-Admins" \
  --model llama3.1:8b

# Get LLM recommendations
python cli.py recommend data.csv --context "Finance team"

# Explanation with recommendations and CSV output only
python cli.py explain data.csv \
  --id-column user_id \
  --recommend \
  --output-format csv \
  --output results
```
