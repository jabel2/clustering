# context.py - LLM Context Builder

**File**: `src/outlier_detector/explanation/context.py`
**Module**: `outlier_detector.explanation`
**Purpose**: Build structured, formatted context/prompts for the LLM explanation agent from clustering and profiling results.

---

## Overview

`context.py` is the bridge between the statistical analysis (clustering, profiling, deviation scoring) and the LLM explanation agent. It takes all the analysis outputs and formats them into a clear, structured prompt that instructs the LLM to explain each outlier.

The prompt is designed to give the LLM everything it needs:
- Dataset context (size, number of clusters, description).
- Cluster profiles (what "normal" looks like).
- Per-outlier details (attribute values, specific deviations from the norm).
- Clear instructions on what to produce (explanation, risk assessment, JSON block).

---

## Data Classes

### `OutlierContext`

Context for a single outlier.

| Field          | Type                | Description                                        |
|----------------|---------------------|----------------------------------------------------|
| `identifier`   | `str`               | Human-readable ID (e.g., `"OUT_3"` or `"Record 1"`). |
| `outlier_score` | `float`            | GLOSH outlier score (0-1).                         |
| `values`       | `dict[str, str]`    | All attribute values for this record.              |
| `deviations`   | `dict[str, dict]`   | Per-column deviation details from the majority cluster. |

### `ExplanationContext`

Complete context for the LLM.

| Field             | Type                   | Description                              |
|-------------------|------------------------|------------------------------------------|
| `dataset_context` | `str`                  | Formatted dataset description.           |
| `cluster_summary` | `str`                  | Formatted cluster profiles.              |
| `outliers`        | `list[OutlierContext]` | Per-outlier context objects.             |
| `prompt`          | `str`                  | The complete, ready-to-send LLM prompt.  |

---

## Public API

### `ContextBuilder(dataset_description="", id_column=None, max_outliers=25)`

**Constructor Parameters**:

| Parameter              | Type          | Default | Description                                                |
|------------------------|---------------|---------|------------------------------------------------------------|
| `dataset_description`  | `str`         | `""`    | Human-readable dataset description (e.g., `"AD group: Finance-Admins"`). |
| `id_column`            | `str \| None` | `None`  | Name of the ID column.                                     |
| `max_outliers`         | `int`         | `25`    | Maximum number of outliers to include in the LLM prompt.   |

### `build(original_df, profile_result, outlier_df, deviation_df, ids=None) -> ExplanationContext`

Builds the complete context for the LLM.

**Parameters**:

| Parameter        | Type              | Description                                      |
|------------------|-------------------|--------------------------------------------------|
| `original_df`    | `pd.DataFrame`    | Original dataset (for record count, context).    |
| `profile_result` | `ProfileResult`   | Cluster profiling result from `ClusterProfiler`. |
| `outlier_df`     | `pd.DataFrame`    | Outlier rows (from `OutlierScorer.get_outlier_data()`). |
| `deviation_df`   | `pd.DataFrame`    | Deviation data (from `ClusterProfiler.compute_deviation_scores()`). |
| `ids`            | `pd.Series \| None` | Outlier identifiers.                          |

**Returns**: `ExplanationContext` with all sections and the complete prompt.

---

## Internal Functions

### `_build_dataset_context(df, profile_result) -> str`

Produces a short summary:
```
Dataset: AD group: Finance-Admins
Total records: 1000
Clusters found: 3
```

### `_build_cluster_summary(profile_result) -> str`

Produces a formatted description of each cluster:
```
**Cluster 0 (850 records, 85.0%)**
  - department: IT: 35%, Sales: 28%, HR: 20%
  - tenure_days: median=1200, range=[100, 2500]

**Noise/Outliers (15 records, 1.5%)**
  - department: IT: 40%, Marketing: 27%
```

Categorical columns show top-3 value distributions. Numerical columns show median and range.

### `_build_outlier_contexts(outlier_df, deviation_df, ids) -> list[OutlierContext]`

Creates an `OutlierContext` for each outlier row:
- Determines identifier (from IDs series or fallback to `"Record N"`).
- Extracts outlier score (from `_outlier_score` column).
- Extracts attribute values (excluding internal `_`-prefixed columns).
- Extracts deviations from the deviation DataFrame.

### `_build_prompt(dataset_context, cluster_summary, outliers, max_outliers=25) -> str`

Constructs the final LLM prompt. This is the most important function.

**Prompt structure**:
1. **Role instruction**: "You are analyzing a dataset to explain why certain records are outliers."
2. **Dataset Context section**: From `_build_dataset_context()`.
3. **Cluster Profiles section**: From `_build_cluster_summary()`.
4. **Outliers to Explain section**: For each outlier:
   - Header with identifier and score.
   - Up to 10 attributes listed.
   - Key deviations from the majority with specific values.
5. **Task instructions**: Asks for explanation, unusual attributes, risk assessment, and recommended action.
6. **JSON format specification**: Requires a fenced JSON code block with structured analysis per outlier.

**Truncation behavior**: If there are more than `max_outliers` outliers:
- Sorts by outlier score (highest first).
- Takes only the top `max_outliers`.
- Adds a note: `"Showing top 25 outliers by score (out of 150 total)."`.

**Attribute limiting**: Each outlier shows a maximum of 10 attributes (the first 10 columns). This prevents prompt overflow for wide datasets.

---

## Assumptions and Limitations

1. **`max_outliers=25` default**: Limits the prompt to 25 outliers. For datasets with hundreds of outliers, only the most extreme are explained. The CLI allows overriding this with `--max-outliers-llm`.
2. **Attribute limit of 10**: Only the first 10 column values are shown per outlier in the prompt. Columns beyond this are silently omitted.
3. **Deviation data alignment**: Assumes `deviation_df` rows align positionally with `outlier_df` rows (same order, same count).
4. **Prompt size**: For 25 outliers with 10 attributes and deviations each, the prompt can easily reach 5,000-10,000 characters. LLMs with small context windows may struggle.
5. **No token counting**: The builder does not estimate or enforce token limits. The agent logs prompt character length for debugging.
6. **LLM is instructed to produce JSON**: The prompt explicitly requests a `json` fenced code block. Model compliance varies.
7. **Deviation formatting**: Categorical deviations show frequency in majority; numerical deviations show z-score. There's no unified severity metric.

---

## Dependencies

- `pandas`
- `..clustering.profiler.ProfileResult`
- `..clustering.profiler.ClusterProfile`

---

## Usage Example

```python
from outlier_detector.explanation import ContextBuilder

builder = ContextBuilder(
    dataset_description="AD group: Finance-Admins",
    id_column="user_id",
    max_outliers=10,
)

context = builder.build(
    original_df=cleaned_df,
    profile_result=profile_result,
    outlier_df=outlier_df,
    deviation_df=deviation_df,
    ids=outlier_info.ids,
)

print(len(context.prompt))  # e.g., 5200 characters
print(context.outliers[0].identifier)  # "OUT_3"
```

---

## Prompt Template (Simplified)

```
You are analyzing a dataset to explain why certain records are outliers.

## Dataset Context
Dataset: AD group: Finance-Admins
Total records: 1000
Clusters found: 3

## Cluster Profiles
**Cluster 0 (850 records, 85.0%)**
  - department: IT: 35%, Sales: 28%
  - tenure_days: median=1200, range=[100, 2500]
...

## Outliers to Explain

### OUT_3 (outlier score: 0.98)
Attributes:
  - department: Marketing
  - tenure_days: 15000
Key deviations from the majority:
  - tenure_days: value 15000 (majority median: 1200, z-score: 8.5)
...

## Your Task
For each outlier, provide:
1. A clear explanation of why this record doesn't fit
2. Which specific attributes make it unusual
3. A risk assessment (Low/Medium/High)
4. A recommended action

IMPORTANT: Include a JSON block with structured data...
```
