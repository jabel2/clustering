"""Analyze dataset structure for LLM recommendations."""

from dataclasses import dataclass, field

import pandas as pd
import numpy as np


@dataclass
class ColumnInfo:
    """Information about a single column."""

    name: str
    dtype: str  # "categorical", "numerical", "boolean", "text"
    unique_count: int
    null_count: int
    null_pct: float
    sample_values: list[str]
    # For numerical columns
    min_val: float | None = None
    max_val: float | None = None
    mean_val: float | None = None
    median_val: float | None = None
    std_val: float | None = None
    # For categorical columns
    top_values: dict[str, float] = field(default_factory=dict)  # value -> percentage


@dataclass
class DatasetProfile:
    """Complete profile of a dataset."""

    n_rows: int
    n_columns: int
    columns: list[ColumnInfo]
    sample_rows: list[dict]
    id_column_candidates: list[str]


class DatasetAnalyzer:
    """Analyze dataset structure to help LLM make recommendations."""

    def __init__(
        self,
        max_sample_values: int = 5,
        max_sample_rows: int = 3,
        max_top_values: int = 5,
    ):
        """Initialize analyzer.

        Args:
            max_sample_values: Max sample values to include per column.
            max_sample_rows: Max sample rows to include.
            max_top_values: Max top categorical values to include.
        """
        self.max_sample_values = max_sample_values
        self.max_sample_rows = max_sample_rows
        self.max_top_values = max_top_values

    def analyze(self, df: pd.DataFrame) -> DatasetProfile:
        """Analyze a DataFrame and return its profile.

        Args:
            df: DataFrame to analyze.

        Returns:
            DatasetProfile with column info and samples.
        """
        columns = []

        for col in df.columns:
            col_info = self._analyze_column(df, col)
            columns.append(col_info)

        # Get sample rows (convert to strings for JSON serialization)
        sample_df = df.head(self.max_sample_rows)
        sample_rows = []
        for _, row in sample_df.iterrows():
            sample_rows.append({k: str(v) for k, v in row.items()})

        # Find ID column candidates (high uniqueness, likely identifiers)
        id_candidates = self._find_id_candidates(df, columns)

        return DatasetProfile(
            n_rows=len(df),
            n_columns=len(df.columns),
            columns=columns,
            sample_rows=sample_rows,
            id_column_candidates=id_candidates,
        )

    def _analyze_column(self, df: pd.DataFrame, col: str) -> ColumnInfo:
        """Analyze a single column."""
        series = df[col]
        unique_count = series.nunique()
        null_count = series.isna().sum()
        null_pct = (null_count / len(df)) * 100 if len(df) > 0 else 0

        # Determine dtype
        dtype = self._infer_dtype(series, unique_count, len(df))

        # Get sample values (non-null)
        non_null = series.dropna()
        sample_values = [str(v) for v in non_null.head(self.max_sample_values).tolist()]

        # Initialize column info
        col_info = ColumnInfo(
            name=col,
            dtype=dtype,
            unique_count=unique_count,
            null_count=null_count,
            null_pct=null_pct,
            sample_values=sample_values,
        )

        # Add type-specific info
        if dtype == "numerical":
            col_info.min_val = float(non_null.min()) if len(non_null) > 0 else None
            col_info.max_val = float(non_null.max()) if len(non_null) > 0 else None
            col_info.mean_val = float(non_null.mean()) if len(non_null) > 0 else None
            col_info.median_val = float(non_null.median()) if len(non_null) > 0 else None
            col_info.std_val = float(non_null.std()) if len(non_null) > 0 else None

        elif dtype == "categorical":
            # Get top values with percentages
            value_counts = series.value_counts(normalize=True).head(self.max_top_values)
            col_info.top_values = {
                str(k): round(v * 100, 1) for k, v in value_counts.items()
            }

        return col_info

    def _infer_dtype(self, series: pd.Series, unique_count: int, n_rows: int) -> str:
        """Infer the semantic type of a column."""
        # Check if boolean
        non_null = series.dropna()
        unique_vals = set(non_null.unique())

        if unique_vals <= {0, 1, True, False, "0", "1", "true", "false", "True", "False"}:
            return "boolean"

        # Check if numerical
        if pd.api.types.is_numeric_dtype(series):
            return "numerical"

        # Check if it's likely text (high cardinality strings, long values)
        if unique_count > 0.5 * n_rows:
            avg_len = non_null.astype(str).str.len().mean()
            if avg_len > 50:  # Long strings are likely text
                return "text"

        return "categorical"

    def _find_id_candidates(
        self, df: pd.DataFrame, columns: list[ColumnInfo]
    ) -> list[str]:
        """Find columns that are likely ID columns."""
        candidates = []

        for col_info in columns:
            # ID columns typically have very high uniqueness
            uniqueness = col_info.unique_count / len(df) if len(df) > 0 else 0

            # Check for ID-like names
            name_lower = col_info.name.lower()
            has_id_name = any(
                term in name_lower
                for term in ["id", "key", "uuid", "guid", "identifier", "code"]
            )

            # High uniqueness (>90%) or ID-like name with decent uniqueness
            if uniqueness > 0.9 or (has_id_name and uniqueness > 0.5):
                candidates.append(col_info.name)

        return candidates

    def to_prompt_text(self, profile: DatasetProfile) -> str:
        """Convert profile to text for LLM prompt.

        Args:
            profile: DatasetProfile to convert.

        Returns:
            Formatted text describing the dataset.
        """
        lines = [
            f"Dataset: {profile.n_rows} rows, {profile.n_columns} columns",
            "",
            "## Columns",
        ]

        for col in profile.columns:
            col_line = f"- **{col.name}** ({col.dtype})"

            if col.null_pct > 0:
                col_line += f" [{col.null_pct:.1f}% null]"

            col_line += f" - {col.unique_count} unique values"
            lines.append(col_line)

            if col.dtype == "numerical" and col.mean_val is not None:
                lines.append(
                    f"  Range: [{col.min_val:.2f}, {col.max_val:.2f}], "
                    f"Mean: {col.mean_val:.2f}, Std: {col.std_val:.2f}"
                )
            elif col.dtype == "categorical" and col.top_values:
                top_str = ", ".join(
                    f"'{k}': {v}%" for k, v in list(col.top_values.items())[:3]
                )
                lines.append(f"  Top values: {top_str}")
            elif col.sample_values:
                samples = ", ".join(f"'{v}'" for v in col.sample_values[:3])
                lines.append(f"  Examples: {samples}")

        if profile.id_column_candidates:
            lines.append("")
            lines.append(
                f"Likely ID columns: {', '.join(profile.id_column_candidates)}"
            )

        if profile.sample_rows:
            lines.append("")
            lines.append("## Sample Rows")
            for i, row in enumerate(profile.sample_rows, 1):
                row_str = ", ".join(f"{k}={v}" for k, v in list(row.items())[:6])
                if len(row) > 6:
                    row_str += ", ..."
                lines.append(f"{i}. {row_str}")

        return "\n".join(lines)
