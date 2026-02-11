"""Build structured context for LLM explanations."""

from dataclasses import dataclass

import pandas as pd

from ..clustering.profiler import ProfileResult, ClusterProfile


@dataclass
class OutlierContext:
    """Context for a single outlier."""

    identifier: str
    outlier_score: float
    values: dict[str, str]
    deviations: dict[str, dict]


@dataclass
class ExplanationContext:
    """Complete context for LLM explanation."""

    dataset_context: str
    cluster_summary: str
    outliers: list[OutlierContext]
    prompt: str


class ContextBuilder:
    """Build structured context for LLM explanations."""

    def __init__(
        self,
        dataset_description: str = "",
        id_column: str | None = None,
        max_outliers: int = 25,
    ):
        """Initialize context builder.

        Args:
            dataset_description: Human-readable description of the dataset
                (e.g., "AD group: Finance-Admins").
            id_column: Name of the ID column for referencing outliers.
            max_outliers: Maximum outliers to include in LLM prompt.
        """
        self.dataset_description = dataset_description
        self.id_column = id_column
        self.max_outliers = max_outliers

    def build(
        self,
        original_df: pd.DataFrame,
        profile_result: ProfileResult,
        outlier_df: pd.DataFrame,
        deviation_df: pd.DataFrame,
        ids: pd.Series | None = None,
    ) -> ExplanationContext:
        """Build complete context for LLM.

        Args:
            original_df: Original dataset.
            profile_result: Cluster profiling result.
            outlier_df: DataFrame with outlier rows.
            deviation_df: DataFrame with deviation information.
            ids: Series of outlier IDs.

        Returns:
            ExplanationContext ready for LLM.
        """
        # Build dataset context
        dataset_context = self._build_dataset_context(
            original_df, profile_result
        )

        # Build cluster summary
        cluster_summary = self._build_cluster_summary(profile_result)

        # Build outlier contexts
        outliers = self._build_outlier_contexts(
            outlier_df, deviation_df, ids
        )

        # Build the full prompt
        prompt = self._build_prompt(
            dataset_context, cluster_summary, outliers, self.max_outliers
        )

        return ExplanationContext(
            dataset_context=dataset_context,
            cluster_summary=cluster_summary,
            outliers=outliers,
            prompt=prompt,
        )

    def _build_dataset_context(
        self,
        df: pd.DataFrame,
        profile_result: ProfileResult,
    ) -> str:
        """Build dataset description section."""
        lines = []

        if self.dataset_description:
            lines.append(f"Dataset: {self.dataset_description}")

        lines.append(f"Total records: {len(df)}")
        lines.append(f"Clusters found: {profile_result.n_clusters}")

        return "\n".join(lines)

    def _build_cluster_summary(self, profile_result: ProfileResult) -> str:
        """Build cluster summary section."""
        lines = []

        for cluster in profile_result.clusters:
            if cluster.label == -1:
                lines.append(f"\n**Noise/Outliers ({cluster.size} records, {cluster.percentage:.1f}%)**")
            else:
                lines.append(f"\n**Cluster {cluster.label} ({cluster.size} records, {cluster.percentage:.1f}%)**")

            for col_profile in cluster.columns:
                if col_profile.dtype == "categorical":
                    dist_str = ", ".join(
                        f"{k}: {v}%" for k, v in list(col_profile.distribution.items())[:3]
                    )
                    lines.append(f"  - {col_profile.name}: {dist_str}")
                else:
                    lines.append(
                        f"  - {col_profile.name}: median={col_profile.distribution['median']}, "
                        f"range=[{col_profile.distribution['min']}, {col_profile.distribution['max']}]"
                    )

        return "\n".join(lines)

    def _build_outlier_contexts(
        self,
        outlier_df: pd.DataFrame,
        deviation_df: pd.DataFrame,
        ids: pd.Series | None,
    ) -> list[OutlierContext]:
        """Build context for each outlier."""
        outliers = []

        for i, (_, row) in enumerate(outlier_df.iterrows()):
            # Determine identifier
            if ids is not None and i < len(ids):
                identifier = str(ids.iloc[i])
            else:
                identifier = f"Record {i+1}"

            # Get score
            score = row.get("_outlier_score", 0)

            # Get values (exclude internal columns)
            values = {
                k: str(v) for k, v in row.items()
                if not k.startswith("_")
            }

            # Get deviations
            deviations = {}
            if i < len(deviation_df):
                dev_row = deviation_df.iloc[i]
                if "deviations" in dev_row:
                    deviations = dev_row["deviations"]

            outliers.append(OutlierContext(
                identifier=identifier,
                outlier_score=float(score),
                values=values,
                deviations=deviations,
            ))

        return outliers

    def _build_prompt(
        self,
        dataset_context: str,
        cluster_summary: str,
        outliers: list[OutlierContext],
        max_outliers: int = 25,
    ) -> str:
        """Build the full LLM prompt."""
        # Limit outliers to prevent prompt from being too long
        total_outliers = len(outliers)
        if total_outliers > max_outliers:
            # Sort by outlier score (highest first) and take top N
            outliers = sorted(outliers, key=lambda x: x.outlier_score, reverse=True)[:max_outliers]
            truncated_note = f"\n\n*Note: Showing top {max_outliers} outliers by score (out of {total_outliers} total).*\n"
        else:
            truncated_note = ""

        outlier_details = []
        for outlier in outliers:
            lines = [f"\n### {outlier.identifier} (outlier score: {outlier.outlier_score:.2f})"]
            lines.append("Attributes:")
            for k, v in list(outlier.values.items())[:10]:  # Limit to 10 attributes
                lines.append(f"  - {k}: {v}")

            if outlier.deviations:
                lines.append("Key deviations from the majority:")
                for col, dev in outlier.deviations.items():
                    if "majority_value" in dev:
                        lines.append(
                            f"  - {col}: has '{dev['outlier_value']}' "
                            f"(majority has '{dev['majority_value']}', "
                            f"only {dev['frequency_in_majority']}% share this value)"
                        )
                    elif "z_score" in dev:
                        lines.append(
                            f"  - {col}: value {dev['outlier_value']} "
                            f"(majority median: {dev['majority_median']}, "
                            f"z-score: {dev['z_score']})"
                        )

            outlier_details.append("\n".join(lines))

        prompt = f"""You are analyzing a dataset to explain why certain records are outliers.

## Dataset Context
{dataset_context}

## Cluster Profiles
{cluster_summary}

## Outliers to Explain{truncated_note}
{"".join(outlier_details)}

## Your Task
For each outlier, provide:
1. A clear explanation of why this record doesn't fit with the majority
2. Which specific attributes make it unusual
3. A risk assessment (Low/Medium/High) for whether this record might be incorrectly included
4. A recommended action (Review, Flag for removal, Likely legitimate exception)

Be concise but specific. Focus on the most significant deviations.

IMPORTANT: After your analysis, you MUST include a JSON block with structured data for each outlier.
Format it exactly like this (with the ```json markers):

```json
[
  {{
    "id": "outlier_id",
    "why_outlier": "Brief explanation",
    "unusual_attributes": "attr1, attr2, attr3",
    "risk_level": "Low|Medium|High",
    "recommended_action": "Review|Flag for removal|Likely legitimate"
  }}
]
```
"""
        return prompt
