"""Data cleaning utilities for handling missing values and type coercion."""

import pandas as pd
import numpy as np


def clean_data(
    df: pd.DataFrame,
    id_column: str | None = None,
    exclude_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.Series | None]:
    """Clean data by handling missing values and preparing for feature engineering.

    Args:
        df: Input DataFrame.
        id_column: Column to use as row identifier (will be extracted, not processed).
        exclude_columns: Columns to exclude from processing.

    Returns:
        Tuple of (cleaned DataFrame, ID series or None).
    """
    df = df.copy()
    exclude = set(exclude_columns or [])

    # Extract ID column if specified
    ids = None
    if id_column and id_column in df.columns:
        ids = df[id_column].copy()
        exclude.add(id_column)

    # Remove excluded columns from processing
    columns_to_process = [c for c in df.columns if c not in exclude]
    df = df[columns_to_process]

    # Handle missing values
    df = _handle_missing_values(df)

    # Coerce types
    df = _coerce_types(df)

    return df, ids


def _handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Handle missing values based on column type."""
    for col in df.columns:
        if df[col].isna().sum() == 0:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            # Fill numeric with median (robust to outliers)
            df[col] = df[col].fillna(df[col].median())
        else:
            # Fill categorical with mode or 'Unknown'
            mode = df[col].mode()
            fill_value = mode.iloc[0] if len(mode) > 0 else "Unknown"
            df[col] = df[col].fillna(fill_value)

    return df


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce columns to appropriate types."""
    for col in df.columns:
        # Try to convert object columns that look like numbers
        if df[col].dtype == object:
            # Check if it's actually numeric
            try:
                numeric = pd.to_numeric(df[col], errors="coerce")
                if numeric.notna().sum() / len(numeric) > 0.9:
                    df[col] = numeric.fillna(numeric.median())
            except (ValueError, TypeError):
                pass

        # Convert boolean-like columns
        if df[col].dtype == object:
            unique_vals = df[col].dropna().unique()
            if len(unique_vals) == 2:
                lower_vals = {str(v).lower() for v in unique_vals}
                if lower_vals <= {"true", "false", "yes", "no", "1", "0", "y", "n"}:
                    df[col] = df[col].map(
                        lambda x: str(x).lower() in ("true", "yes", "1", "y")
                    ).astype(int)

    return df
