# recommender.py - LLM-Based Settings Recommender

**File**: `src/outlier_detector/recommendation/recommender.py`
**Module**: `outlier_detector.recommendation`
**Purpose**: Use a local Ollama LLM to recommend optimal outlier detection settings based on dataset structure and domain context.

---

## Overview

`recommender.py` is the "smart configuration" module. Instead of requiring users to manually specify column types, thresholds, and clustering parameters, it sends a structured description of the dataset to an LLM and asks it to recommend settings. The LLM receives:
- Column profiles (types, cardinality, distributions, statistics).
- Sample data rows.
- Optional domain context (e.g., "Active Directory group for Finance team").

The LLM responds with a JSON block containing recommended settings, which are parsed and used to generate ready-to-use CLI commands.

---

## Data Classes

### `RecommendedSettings`

Recommended settings from LLM analysis.

| Field                  | Type                | Default       | Description                                              |
|------------------------|---------------------|---------------|----------------------------------------------------------|
| `id_column`            | `str \| None`       | `None`        | Column to use as row identifier.                         |
| `categorical_columns`  | `list[str]`         | `[]`          | Columns to treat as categorical.                         |
| `numerical_columns`    | `list[str]`         | `[]`          | Columns to treat as numerical.                           |
| `exclude_columns`      | `list[str]`         | `[]`          | Columns to exclude from analysis.                        |
| `expected_outlier_pct` | `float \| None`     | `None`        | Expected percentage of outliers.                         |
| `auto_method`          | `str`               | `"heuristic"` | Recommended auto-tuning method (`"heuristic"`, `"balanced"`, `"dbcv"`). |
| `min_cluster_size`     | `int \| None`       | `None`        | Specific min_cluster_size (if not using auto).           |
| `column_weights`       | `dict[str, float]`  | `{}`          | Importance weights for columns (>1.0 = more important).  |
| `outlier_signals`      | `list[str]`         | `[]`          | Domain-specific outlier patterns to watch for.           |
| `reasoning`            | `str`               | `""`          | LLM's reasoning for its recommendations.                 |

### `RecommendationResult`

Full result from the LLM recommendation.

| Field          | Type                  | Description                                          |
|----------------|-----------------------|------------------------------------------------------|
| `settings`     | `RecommendedSettings` | Parsed recommended settings.                         |
| `raw_response` | `str`                 | Raw LLM response text.                               |
| `model`        | `str`                 | Model name used.                                     |
| `cli_command`  | `str`                 | Generated CLI command string.                        |

---

## Public API

### `SettingsRecommender(model="gpt-oss:20b", host="http://localhost:11434", temperature=0.1)`

**Constructor Parameters**:

| Parameter     | Type    | Default                      | Description                    |
|---------------|---------|------------------------------|--------------------------------|
| `model`       | `str`   | `"gpt-oss:20b"`             | Ollama model name.             |
| `host`        | `str`   | `"http://localhost:11434"`   | Ollama API server URL.         |
| `temperature` | `float` | `0.1`                        | Sampling temperature.          |

### `recommend(profile, domain_context="", file_path="") -> RecommendationResult`

Gets LLM recommendations for outlier detection settings.

**Parameters**:

| Parameter        | Type              | Default | Description                                            |
|------------------|-------------------|---------|--------------------------------------------------------|
| `profile`        | `DatasetProfile`  | -       | Dataset profile from `DatasetAnalyzer.analyze()`.      |
| `domain_context` | `str`             | `""`    | Domain description (e.g., `"Finance team AD group"`).  |
| `file_path`      | `str`             | `""`    | Path to data file (used in generated CLI command).     |

**Returns**: `RecommendationResult` with parsed settings and CLI command.

**Raises**: `ConnectionError` if Ollama is not running.

**System prompt**: The LLM receives:
> "You are a data science expert specializing in anomaly detection and clustering. You help users configure outlier detection tools by analyzing their datasets and recommending optimal settings. Be specific and practical in your recommendations."

### `check_connection() -> bool`

Checks if Ollama is available.

---

## Internal Functions

### `_build_prompt(profile, domain_context) -> str`

Constructs the LLM prompt containing:
1. Dataset profile text (via `DatasetAnalyzer.to_prompt_text()`).
2. Optional domain context section.
3. Detailed instructions with the expected JSON response format.
4. Guidelines for each setting (what to consider when recommending).

### `_sanitize_text(text) -> str`

Sanitizes text for Windows console compatibility. Replaces Unicode characters that cause `UnicodeEncodeError` on `cp1252` (Windows default encoding):
- Smart quotes -> ASCII quotes
- En/em dashes -> hyphens
- Ellipsis -> `...`
- Non-breaking spaces -> regular spaces
- Any remaining non-`cp1252` characters -> `?`

### `_parse_settings(response, profile) -> RecommendedSettings`

Parses the LLM's JSON response block into a `RecommendedSettings` object.

**Parsing strategy**:
1. Search for ` ```json ... ``` ` fenced code block.
2. If not found, search for ` ``` {...} ``` ` (object in generic code block).
3. Parse JSON and extract all settings fields.
4. Apply `_sanitize_text()` to string fields (`outlier_signals`, `reasoning`).

**Fallback**: If JSON parsing fails entirely, returns a `RecommendedSettings` with:
- `reasoning` set to `"Could not parse structured response."`.
- `id_column` set to the first candidate from the dataset profile (if any).

### `_build_cli_command(settings, file_path) -> str`

Generates a ready-to-use CLI command string. Example output:
```
python cli.py analyze \
  data/samples/test_data.csv \
  --id-column user_id \
  --categorical "department,location,job_title" \
  --numerical "tenure_days,manager_level" \
  --auto-cluster-size \
  --auto-method heuristic
```

**Path handling**: If `file_path` contains `"clustering\\"`, it extracts the relative portion and converts backslashes to forward slashes.

---

## Assumptions and Limitations

1. **Requires Ollama with a capable model**: The quality of recommendations depends entirely on the LLM. Smaller models may produce poor or invalid JSON.
2. **`num_predict=2000`**: The LLM response is capped at 2000 tokens, which may truncate detailed reasoning.
3. **JSON parsing is brittle**: Depends on the LLM producing a properly-formatted JSON block. No fuzzy JSON parsing or JSON repair is attempted.
4. **`column_weights` are advisory**: The generated CLI command doesn't actually apply column weights because the feature engineering module doesn't support weighted features. The weights are informational only.
5. **Windows-specific text sanitization**: The `_sanitize_text()` function is tailored for Windows `cp1252` encoding. On Linux/Mac systems, this sanitization is harmless but unnecessary.
6. **CLI command always uses `analyze`**: The generated command uses the `analyze` subcommand, not `explain`. The CLI module modifies it to `explain` when showing the extended command.
7. **Path handling is Windows-specific**: The backslash splitting in `_build_cli_command()` assumes Windows paths.

---

## Dependencies

- `json` (stdlib)
- `re` (stdlib)
- `ollama`
- `.analyzer.DatasetProfile`
- `.analyzer.DatasetAnalyzer`

---

## Usage Example

```python
from outlier_detector.recommendation import DatasetAnalyzer, SettingsRecommender

# Analyze dataset
analyzer = DatasetAnalyzer()
profile = analyzer.analyze(df)

# Get recommendations
recommender = SettingsRecommender(model="llama3.1:8b")
if recommender.check_connection():
    result = recommender.recommend(
        profile=profile,
        domain_context="Active Directory group for Finance team",
        file_path="data/samples/finance_group.csv",
    )

    print(f"ID column: {result.settings.id_column}")
    print(f"Categorical: {result.settings.categorical_columns}")
    print(f"CLI command:\n{result.cli_command}")
```

---

## Data Flow

```
DatasetProfile (from analyzer.py) + domain context string
    |
    v
SettingsRecommender.recommend(profile, domain_context, file_path)
    |
    +---> _build_prompt(): Create LLM prompt with dataset profile
    |
    +---> Ollama API: system prompt + user prompt
    |
    +---> _parse_settings(): Extract JSON from response
    |
    +---> _build_cli_command(): Generate CLI command
    |
    v
RecommendationResult
    .settings: RecommendedSettings(id_column="user_id", ...)
    .cli_command: "python cli.py analyze ..."
    .raw_response: "Based on the dataset..."
    |
    v
[Used by CLI for terminal display and command suggestions]
```
