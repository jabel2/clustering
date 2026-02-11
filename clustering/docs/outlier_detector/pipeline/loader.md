# loader.py - Data Loading Utilities

**File**: `src/outlier_detector/pipeline/loader.py`
**Module**: `outlier_detector.pipeline`
**Purpose**: Load tabular data from CSV and JSON files into Pandas DataFrames.

---

## Overview

`loader.py` is the entry point for all data ingestion in the outlier detection pipeline. It provides a single public function, `load_data()`, that accepts a file path and returns a `pandas.DataFrame`. The module supports CSV and JSON formats and handles several JSON structural variations.

---

## Public API

### `load_data(file_path: str | Path) -> pd.DataFrame`

Loads data from a CSV or JSON file and returns it as a DataFrame.

**Parameters**:

| Parameter   | Type           | Description                          |
|-------------|----------------|--------------------------------------|
| `file_path` | `str \| Path`  | Path to the data file (CSV or JSON). |

**Returns**: `pd.DataFrame` containing the loaded data.

**Raises**:
- `FileNotFoundError` - If the specified file does not exist on disk.
- `ValueError` - If the file extension is not `.csv` or `.json`.

**Behavior by file type**:

| Extension | Loading Method                | Notes                          |
|-----------|-------------------------------|--------------------------------|
| `.csv`    | `pd.read_csv(path)`          | Standard Pandas CSV reader.    |
| `.json`   | Custom `_load_json()` parser | Handles multiple JSON layouts. |

---

## Internal Functions

### `_load_json(path: Path) -> pd.DataFrame`

Handles three JSON formats:

1. **Array of objects** (most common):
   ```json
   [{"col1": "val1", "col2": "val2"}, ...]
   ```
   Directly converted to a DataFrame via `pd.DataFrame(data)`.

2. **Object with a `"data"` key** containing an array:
   ```json
   {"data": [{"col1": "val1"}, ...], "metadata": {...}}
   ```
   Extracts and converts only the `data` array.

3. **Single object** (fallback):
   ```json
   {"col1": "val1", "col2": "val2"}
   ```
   Wrapped in a list and converted to a single-row DataFrame.

**Raises**: `ValueError` if the JSON root is neither a list nor a dict.

---

## Assumptions and Limitations

1. **File extension determines format**: The loader relies entirely on the `.csv` or `.json` suffix. A CSV file named `data.txt` will be rejected even if its content is valid CSV.
2. **CSV uses default Pandas parsing**: No custom delimiter, encoding, or quoting options are exposed. Files must be standard comma-delimited, UTF-8 compatible CSV.
3. **JSON must be UTF-8 encoded**: The JSON reader opens files with `encoding="utf-8"` explicitly.
4. **No streaming or chunking**: The entire file is loaded into memory at once. Very large files may cause memory issues.
5. **No schema validation**: The loader does not validate that the loaded data has expected columns or types. Downstream modules (cleaner, features) handle this.
6. **Excel, Parquet, and other formats are not supported**.

---

## Dependencies

- `json` (stdlib)
- `pathlib.Path` (stdlib)
- `pandas`

---

## Usage Example

```python
from outlier_detector.pipeline import load_data

# Load a CSV file
df = load_data("data/samples/ad_test_data.csv")

# Load a JSON file
df = load_data("data/samples/users.json")
```

---

## Data Flow

```
File on disk (.csv or .json)
    |
    v
load_data()
    |
    v
pd.DataFrame (raw, uncleaned)
    |
    v
[Next step: clean_data() in cleaner.py]
```
