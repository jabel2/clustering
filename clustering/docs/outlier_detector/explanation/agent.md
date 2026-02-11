# agent.py - LLM Explanation Agent

**File**: `src/outlier_detector/explanation/agent.py`
**Module**: `outlier_detector.explanation`
**Purpose**: Interface with a local Ollama LLM to generate natural-language explanations of detected outliers.

---

## Overview

`agent.py` is the LLM integration layer. It sends structured outlier analysis context to a locally-running Ollama model and parses the response into both a human-readable explanation and structured per-outlier analysis data. The agent handles:
- Connection management with the Ollama server.
- Prompt construction (system + user messages).
- Response parsing (both free text and embedded JSON).
- Model availability checking.

---

## Data Classes

### `OutlierAnalysis`

Structured analysis for a single outlier, parsed from the LLM's JSON response block.

| Field                | Type  | Description                                           |
|----------------------|-------|-------------------------------------------------------|
| `id`                 | `str` | Outlier identifier.                                   |
| `why_outlier`        | `str` | Brief explanation of why the record is an outlier.    |
| `unusual_attributes` | `str` | Comma-separated list of unusual attribute names.      |
| `risk_level`         | `str` | `"Low"`, `"Medium"`, or `"High"`.                    |
| `recommended_action` | `str` | `"Review"`, `"Flag for removal"`, or `"Likely legitimate"`. |

### `ExplanationResult`

Full result from LLM explanation.

| Field                 | Type                      | Description                                |
|-----------------------|---------------------------|--------------------------------------------|
| `explanation`         | `str`                     | Full text explanation from the LLM.        |
| `model`               | `str`                     | Model name used (e.g., `"gpt-oss:20b"`).  |
| `prompt_tokens`       | `int \| None`             | Number of prompt tokens consumed.          |
| `completion_tokens`   | `int \| None`             | Number of completion tokens generated.     |
| `structured_analysis` | `list[OutlierAnalysis]`   | Parsed per-outlier structured data. Empty if JSON parsing fails. |

---

## Public API

### `ExplanationAgent(model="gpt-oss:20b", host="http://localhost:11434", temperature=0.1, max_tokens=4000)`

**Constructor Parameters**:

| Parameter     | Type    | Default                      | Description                                        |
|---------------|---------|------------------------------|----------------------------------------------------|
| `model`       | `str`   | `"gpt-oss:20b"`             | Ollama model name.                                 |
| `host`        | `str`   | `"http://localhost:11434"`   | Ollama API server URL.                             |
| `temperature` | `float` | `0.1`                        | Sampling temperature. Low = deterministic.          |
| `max_tokens`  | `int`   | `4000`                       | Maximum tokens in the LLM response.                |

The constructor immediately creates an `ollama.Client` instance.

### `explain(context: ExplanationContext) -> ExplanationResult`

Sends the outlier context to the LLM and returns the explanation.

**Parameters**:

| Parameter | Type                 | Description                              |
|-----------|----------------------|------------------------------------------|
| `context` | `ExplanationContext` | Built by `ContextBuilder.build()`.       |

**Returns**: `ExplanationResult` with the LLM's explanation and parsed analysis.

**Raises**: `ConnectionError` if Ollama is not running or connection is refused.

**System prompt**: The LLM receives this system message:
> "You are a data analyst specializing in anomaly detection. You explain why certain records are outliers in clear, actionable terms. Be concise and focus on the most significant findings."

**Empty response handling**: If the LLM returns an empty string, a diagnostic message is generated suggesting reducing outlier count or using a model with a larger context window.

**Response format handling**: The method handles both dictionary-style and object-style Ollama response formats for compatibility across Ollama library versions.

### `check_connection() -> bool`

Checks if Ollama is available and the specified model is loaded.

**Returns**: `True` if the connection is successful and the model is found, `False` otherwise.

**Model matching logic**: Compares the base model name (before `:`) against available models. So `"gpt-oss:20b"` matches any model starting with `"gpt-oss"`.

### `list_available_models() -> list[str]`

Lists all models available on the Ollama server.

**Returns**: List of model name strings, or empty list if Ollama is unreachable.

---

## Internal Functions

### `_parse_structured_analysis(explanation) -> list[OutlierAnalysis]`

Extracts structured JSON data from the LLM's response text.

**Parsing strategy**:
1. Search for a ` ```json ... ``` ` fenced code block.
2. If not found, search for ` ``` [...] ``` ` (array in a generic code block).
3. Parse the JSON content.
4. Map each item to an `OutlierAnalysis` dataclass.

**Failure handling**: Returns an empty list if:
- No JSON block is found in the response.
- JSON parsing fails (`JSONDecodeError`).
- Expected keys are missing.

---

## Assumptions and Limitations

1. **Requires a running Ollama server**: The tool will fail if Ollama is not running at the configured host. The default expectation is `localhost:11434`.
2. **Default model is `gpt-oss:20b`**: This is a specific model the developer uses. Users must have this model pulled in Ollama or specify a different one via `--model`.
3. **LLM output quality varies**: The structured JSON parsing depends on the LLM following the prompt's formatting instructions. Smaller or less capable models may not produce valid JSON blocks.
4. **Temperature of 0.1**: Very low temperature means responses are highly deterministic but potentially less creative in analysis.
5. **Token limits**: The `max_tokens=4000` limit may truncate long explanations for datasets with many outliers.
6. **No retry logic**: If the LLM call fails for reasons other than connection errors, the exception propagates up.
7. **Token counts may be `None`**: Depends on the Ollama response format; some models/versions don't report token usage.

---

## Dependencies

- `json` (stdlib)
- `re` (stdlib)
- `ollama`
- `.context.ExplanationContext`

---

## Usage Example

```python
from outlier_detector.explanation import ExplanationAgent, ContextBuilder

# Check connection first
agent = ExplanationAgent(model="llama3.1:8b")
if agent.check_connection():
    result = agent.explain(explanation_context)
    print(result.explanation)

    for analysis in result.structured_analysis:
        print(f"{analysis.id}: {analysis.risk_level} - {analysis.why_outlier}")
else:
    print("Ollama not available")
    print("Available models:", agent.list_available_models())
```

---

## Data Flow

```
ExplanationContext (from context.py)
    |
    v
ExplanationAgent.explain(context)
    |
    +---> Ollama API: system prompt + context.prompt
    |
    +---> Parse response text
    |         - Extract full explanation
    |         - Parse embedded JSON block
    |
    v
ExplanationResult
    .explanation: "## Analysis\n\n### User OUT_3 ..."
    .structured_analysis: [OutlierAnalysis(id="OUT_3", ...)]
    .model: "gpt-oss:20b"
    |
    v
[Used by CLI for terminal display, JSON/Markdown/CSV output]
```
