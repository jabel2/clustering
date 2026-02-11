"""Cluster profiling for generating human-readable descriptions."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .clusterer import ClusterResult


@dataclass
class ColumnProfile:
    """Profile of a single column within a cluster."""

    name: str
    dtype: str
    mode: Any  # Most common value (categorical) or median (numerical)
    mode_percentage: float  # Percentage with the mode value
    distribution: dict[str, float]  # Value distribution or stats


@dataclass
class ClusterProfile:
    """Profile of a single cluster."""

    label: int
    size: int
    percentage: float
    columns: list[ColumnProfile]


@dataclass
class ProfileResult:
    """Complete profiling result."""

    clusters: list[ClusterProfile]
    overall_size: int
    n_clusters: int


class ClusterProfiler:
    """Generate profiles describing each cluster's characteristics."""

    def __init__(
        self,
        categorical_columns: list[str],
        numerical_columns: list[str],
        top_n_categories: int = 5,
    ):
        """Initialize profiler.

        Args:
            categorical_columns: List of categorical column names.
            numerical_columns: List of numerical column names.
            top_n_categories: Number of top categories to include in distribution.
        """
        self.categorical_columns = categorical_columns
        self.numerical_columns = numerical_columns
        self.top_n_categories = top_n_categories

    def profile(
        self,
        df: pd.DataFrame,
        cluster_result: ClusterResult,
    ) -> ProfileResult:
        """Generate profiles for all clusters.

        Args:
            df: Original DataFrame (before encoding).
            cluster_result: Clustering result.

        Returns:
            ProfileResult with profiles for each cluster.
        """
        clusters = []
        unique_labels = sorted(set(cluster_result.labels))

        for label in unique_labels:
            mask = cluster_result.labels == label
            cluster_df = df.iloc[mask]

            size = len(cluster_df)
            percentage = 100 * size / len(df)

            column_profiles = []

            # Profile categorical columns
            for col in self.categorical_columns:
                if col not in df.columns:
                    continue
                profile = self._profile_categorical(cluster_df[col], col)
                column_profiles.append(profile)

            # Profile numerical columns
            for col in self.numerical_columns:
                if col not in df.columns:
                    continue
                profile = self._profile_numerical(cluster_df[col], col)
                column_profiles.append(profile)

            clusters.append(
                ClusterProfile(
                    label=label,
                    size=size,
                    percentage=percentage,
                    columns=column_profiles,
                )
            )

        return ProfileResult(
            clusters=clusters,
            overall_size=len(df),
            n_clusters=cluster_result.n_clusters,
        )

    def _profile_categorical(self, series: pd.Series, name: str) -> ColumnProfile:
        """Profile a categorical column."""
        value_counts = series.value_counts(normalize=True)

        mode = value_counts.index[0] if len(value_counts) > 0 else None
        mode_pct = value_counts.iloc[0] * 100 if len(value_counts) > 0 else 0

        # Top N distribution
        top_n = value_counts.head(self.top_n_categories)
        distribution = {str(k): round(v * 100, 1) for k, v in top_n.items()}

        return ColumnProfile(
            name=name,
            dtype="categorical",
            mode=mode,
            mode_percentage=round(mode_pct, 1),
            distribution=distribution,
        )

    def _profile_numerical(self, series: pd.Series, name: str) -> ColumnProfile:
        """Profile a numerical column."""
        median = series.median()
        mean = series.mean()
        std = series.std()
        min_val = series.min()
        max_val = series.max()

        distribution = {
            "mean": round(mean, 2),
            "median": round(median, 2),
            "std": round(std, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
        }

        return ColumnProfile(
            name=name,
            dtype="numerical",
            mode=round(median, 2),
            mode_percentage=0,  # Not applicable for numerical
            distribution=distribution,
        )

    def compute_deviation_scores(
        self,
        df: pd.DataFrame,
        outlier_indices: np.ndarray,
        cluster_result: ClusterResult,
    ) -> pd.DataFrame:
        """Compute how much each outlier deviates from the majority cluster.

        Args:
            df: Original DataFrame.
            outlier_indices: Indices of outlier rows.
            cluster_result: Clustering result.

        Returns:
            DataFrame with deviation information for each outlier.
        """
        # Find the largest cluster (the "norm")
        labels = cluster_result.labels
        valid_labels = labels[labels != -1]
        if len(valid_labels) == 0:
            # All points are outliers, compare to overall distribution
            majority_mask = np.ones(len(df), dtype=bool)
        else:
            majority_label = pd.Series(valid_labels).mode().iloc[0]
            majority_mask = labels == majority_label

        majority_df = df.iloc[majority_mask]

        deviations = []

        for idx in outlier_indices:
            outlier_row = df.iloc[idx]
            row_deviations = {}

            # Check categorical deviations
            for col in self.categorical_columns:
                if col not in df.columns:
                    continue
                majority_mode = majority_df[col].mode()
                if len(majority_mode) > 0:
                    majority_mode = majority_mode.iloc[0]
                    outlier_val = outlier_row[col]
                    if outlier_val != majority_mode:
                        # Calculate how common the outlier's value is in majority
                        freq = (majority_df[col] == outlier_val).mean()
                        row_deviations[col] = {
                            "outlier_value": outlier_val,
                            "majority_value": majority_mode,
                            "frequency_in_majority": round(freq * 100, 1),
                        }

            # Check numerical deviations
            for col in self.numerical_columns:
                if col not in df.columns:
                    continue
                majority_median = majority_df[col].median()
                majority_std = majority_df[col].std()
                outlier_val = outlier_row[col]

                if majority_std > 0:
                    z_score = abs(outlier_val - majority_median) / majority_std
                    if z_score > 2:  # More than 2 std deviations
                        row_deviations[col] = {
                            "outlier_value": round(outlier_val, 2),
                            "majority_median": round(majority_median, 2),
                            "z_score": round(z_score, 2),
                        }

            deviations.append(row_deviations)

        return pd.DataFrame({"index": outlier_indices, "deviations": deviations})
