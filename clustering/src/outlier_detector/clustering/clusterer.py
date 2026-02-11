"""HDBSCAN clustering wrapper."""

from dataclasses import dataclass

import numpy as np
import hdbscan


@dataclass
class ClusterResult:
    """Result of clustering operation."""

    labels: np.ndarray  # Cluster labels (-1 for noise/outliers)
    probabilities: np.ndarray  # Cluster membership probability
    outlier_scores: np.ndarray  # Outlier score (0-1, higher = more outlier-like)
    n_clusters: int
    n_noise: int


class HDBSCANClusterer:
    """HDBSCAN clustering for outlier detection."""

    def __init__(
        self,
        min_cluster_size: int = 5,
        min_samples: int | None = None,
        metric: str = "euclidean",
        cluster_selection_method: str = "eom",
    ):
        """Initialize HDBSCAN clusterer.

        Args:
            min_cluster_size: Minimum size of clusters. Smaller values detect
                more fine-grained clusters but may be more sensitive to noise.
            min_samples: Minimum samples in neighborhood. If None, uses
                min_cluster_size. Lower values make clustering more liberal.
            metric: Distance metric to use.
            cluster_selection_method: 'eom' (Excess of Mass) for variable density
                or 'leaf' for more homogeneous clusters.
        """
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.metric = metric
        self.cluster_selection_method = cluster_selection_method
        self._clusterer: hdbscan.HDBSCAN | None = None

    def fit(self, features: np.ndarray) -> ClusterResult:
        """Fit HDBSCAN to feature matrix.

        Args:
            features: Feature matrix of shape (n_samples, n_features).

        Returns:
            ClusterResult with labels, probabilities, and outlier scores.
        """
        self._clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric=self.metric,
            cluster_selection_method=self.cluster_selection_method,
            gen_min_span_tree=True,
        )

        self._clusterer.fit(features)

        labels = self._clusterer.labels_
        probabilities = self._clusterer.probabilities_
        outlier_scores = self._clusterer.outlier_scores_

        # Count clusters (excluding noise label -1)
        unique_labels = set(labels)
        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_noise = (labels == -1).sum()

        return ClusterResult(
            labels=labels,
            probabilities=probabilities,
            outlier_scores=outlier_scores,
            n_clusters=n_clusters,
            n_noise=n_noise,
        )

    @property
    def clusterer(self) -> hdbscan.HDBSCAN | None:
        """Access underlying HDBSCAN model."""
        return self._clusterer

    @staticmethod
    def auto_min_cluster_size(
        features: np.ndarray,
        min_value: int = 3,
        max_value: int | None = None,
        method: str = "dbcv",
    ) -> tuple[int, dict]:
        """Automatically determine optimal min_cluster_size.

        Args:
            features: Feature matrix of shape (n_samples, n_features).
            min_value: Minimum value to try.
            max_value: Maximum value to try. If None, uses sqrt(n_samples).
            method: Method for selection:
                - 'dbcv': Use DBCV (relative_validity_) score (recommended)
                - 'heuristic': Use log-based heuristic
                - 'balanced': Find value with reasonable outlier rate (5-15%)

        Returns:
            Tuple of (optimal_min_cluster_size, evaluation_details).
        """
        n_samples = len(features)

        if method == "heuristic":
            # Simple heuristic: log-based scaling
            optimal = max(min_value, int(np.log2(n_samples)))
            return optimal, {"method": "heuristic", "formula": "log2(n_samples)"}

        # Determine search range
        if max_value is None:
            max_value = max(min_value + 1, min(50, int(np.sqrt(n_samples))))

        candidates = list(range(min_value, max_value + 1))

        if method == "dbcv":
            # Try each value and score with DBCV
            # Penalize solutions that don't have meaningful outlier detection
            best_score = -np.inf
            best_size = min_value
            scores = {}

            # Target: we want some noise AND no extreme cluster imbalance
            min_outlier_pct = 1.0  # At least 1% should be outliers (noise + tiny clusters)
            max_dominant_pct = 95.0  # Penalize if one cluster has >95% of data

            for size in candidates:
                try:
                    clusterer = hdbscan.HDBSCAN(
                        min_cluster_size=size,
                        gen_min_span_tree=True,
                    )
                    clusterer.fit(features)

                    labels = clusterer.labels_
                    raw_dbcv = clusterer.relative_validity_

                    # Count noise
                    noise_count = (labels == -1).sum()
                    noise_pct = noise_count / n_samples * 100

                    # Count clusters and their sizes
                    unique_labels = [l for l in set(labels) if l != -1]
                    n_clusters = len(unique_labels)
                    cluster_sizes = [(labels == l).sum() for l in unique_labels]

                    # Calculate "effective outlier %" = noise + tiny clusters
                    # Tiny cluster = less than min_cluster_size * 2 (borderline clusters)
                    tiny_threshold = size * 2
                    tiny_cluster_count = sum(s for s in cluster_sizes if s < tiny_threshold)
                    effective_outlier_pct = (noise_count + tiny_cluster_count) / n_samples * 100

                    # Check for dominant cluster (cluster imbalance)
                    max_cluster_pct = max(cluster_sizes) / n_samples * 100 if cluster_sizes else 0

                    # Start with raw DBCV
                    adjusted_score = raw_dbcv

                    # Penalty 1: Not enough effective outliers
                    if effective_outlier_pct < min_outlier_pct:
                        penalty = 0.5 * (1 - effective_outlier_pct / min_outlier_pct)
                        adjusted_score *= (1 - penalty)

                    # Penalty 2: One cluster dominates too much (>95%)
                    if max_cluster_pct > max_dominant_pct:
                        # Likely absorbed outliers into main cluster
                        penalty = 0.3 * ((max_cluster_pct - max_dominant_pct) / (100 - max_dominant_pct))
                        adjusted_score *= (1 - penalty)

                    # Penalty 3: Only 1 cluster
                    if n_clusters < 2:
                        adjusted_score *= 0.5

                    scores[size] = {
                        "dbcv": float(raw_dbcv),
                        "adjusted_score": float(adjusted_score),
                        "n_clusters": n_clusters,
                        "noise_pct": float(noise_pct),
                        "effective_outlier_pct": float(effective_outlier_pct),
                        "max_cluster_pct": float(max_cluster_pct),
                    }

                    score = adjusted_score
                    if score > best_score:
                        best_score = score
                        best_size = size
                except Exception:
                    continue

            return best_size, {"method": "dbcv", "scores": scores, "best_score": best_score}

        elif method == "balanced":
            # Find value with outlier rate in target range (5-15%)
            target_min, target_max = 0.05, 0.15
            best_size = min_value
            best_diff = float("inf")
            results = {}

            for size in candidates:
                try:
                    clusterer = hdbscan.HDBSCAN(min_cluster_size=size)
                    clusterer.fit(features)

                    noise_rate = (clusterer.labels_ == -1).sum() / n_samples
                    n_clusters = len(set(clusterer.labels_)) - (1 if -1 in clusterer.labels_ else 0)

                    results[size] = {
                        "noise_pct": float(noise_rate * 100),
                        "n_clusters": n_clusters,
                    }

                    # Score: how close to target range (prefer middle of range)
                    if target_min <= noise_rate <= target_max:
                        diff = abs(noise_rate - (target_min + target_max) / 2)
                    else:
                        diff = min(abs(noise_rate - target_min), abs(noise_rate - target_max))

                    if diff < best_diff and n_clusters >= 2:
                        best_diff = diff
                        best_size = size
                except Exception:
                    continue

            return best_size, {"method": "balanced", "target_range": "5-15%", "results": results}

        else:
            raise ValueError(f"Unknown method: {method}")
