"""Outlier scoring and extraction."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .clusterer import ClusterResult


@dataclass
class OutlierInfo:
    """Information about detected outliers."""

    indices: np.ndarray  # Indices of outlier rows
    scores: np.ndarray  # Outlier scores for outliers
    ids: pd.Series | None  # IDs of outliers (if ID column provided)
    total_count: int
    outlier_count: int
    outlier_percentage: float


class OutlierScorer:
    """Score and extract outliers from clustering results."""

    def __init__(
        self,
        outlier_threshold: float = 0.8,
        use_cluster_labels: bool = True,
    ):
        """Initialize outlier scorer.

        Args:
            outlier_threshold: Points with outlier_score >= threshold are outliers.
            use_cluster_labels: If True, also treat cluster=-1 (noise) as outliers.
        """
        self.outlier_threshold = outlier_threshold
        self.use_cluster_labels = use_cluster_labels

    def score(
        self,
        cluster_result: ClusterResult,
        ids: pd.Series | None = None,
    ) -> OutlierInfo:
        """Identify outliers from clustering results.

        Args:
            cluster_result: Result from HDBSCANClusterer.fit().
            ids: Optional series of row identifiers.

        Returns:
            OutlierInfo with outlier indices, scores, and statistics.
        """
        # Combine criteria for outlier detection
        is_outlier_by_score = cluster_result.outlier_scores >= self.outlier_threshold

        if self.use_cluster_labels:
            is_noise = cluster_result.labels == -1
            is_outlier = is_outlier_by_score | is_noise
        else:
            is_outlier = is_outlier_by_score

        outlier_indices = np.where(is_outlier)[0]
        outlier_scores = cluster_result.outlier_scores[outlier_indices]

        # Sort by outlier score (most outlier-like first)
        sort_order = np.argsort(-outlier_scores)
        outlier_indices = outlier_indices[sort_order]
        outlier_scores = outlier_scores[sort_order]

        # Get IDs if provided
        outlier_ids = None
        if ids is not None:
            outlier_ids = ids.iloc[outlier_indices].reset_index(drop=True)

        total = len(cluster_result.labels)
        outlier_count = len(outlier_indices)

        return OutlierInfo(
            indices=outlier_indices,
            scores=outlier_scores,
            ids=outlier_ids,
            total_count=total,
            outlier_count=outlier_count,
            outlier_percentage=100 * outlier_count / total if total > 0 else 0,
        )

    def get_outlier_data(
        self,
        df: pd.DataFrame,
        outlier_info: OutlierInfo,
    ) -> pd.DataFrame:
        """Extract original data rows for outliers.

        Args:
            df: Original DataFrame.
            outlier_info: OutlierInfo from score().

        Returns:
            DataFrame with outlier rows and their scores.
        """
        outlier_df = df.iloc[outlier_info.indices].copy()
        outlier_df["_outlier_score"] = outlier_info.scores
        return outlier_df.reset_index(drop=True)
