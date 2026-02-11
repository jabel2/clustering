"""Data loading utilities for CSV and JSON files."""

import json
from pathlib import Path

import pandas as pd


def load_data(file_path: str | Path) -> pd.DataFrame:
    """Load data from CSV or JSON file.

    Args:
        file_path: Path to the data file (CSV or JSON).

    Returns:
        DataFrame with the loaded data.

    Raises:
        ValueError: If file format is not supported.
        FileNotFoundError: If file does not exist.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)
    elif suffix == ".json":
        return _load_json(path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use CSV or JSON.")


def _load_json(path: Path) -> pd.DataFrame:
    """Load JSON file, handling both array and object formats."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return pd.DataFrame(data)
    elif isinstance(data, dict):
        # Check if it's a records-style dict with a data key
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        # Otherwise treat as single record
        return pd.DataFrame([data])
    else:
        raise ValueError("JSON must contain an array or object")
