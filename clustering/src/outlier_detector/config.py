"""Configuration settings for the outlier detector."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClusteringConfig:
    """Configuration for HDBSCAN clustering."""

    min_cluster_size: int = 5
    min_samples: Optional[int] = None
    metric: str = "euclidean"
    cluster_selection_method: str = "eom"  # 'eom' or 'leaf'


@dataclass
class OutlierConfig:
    """Configuration for outlier detection."""

    outlier_threshold: float = 0.8  # Points with outlier_score >= this are outliers
    use_cluster_labels: bool = True  # Also treat cluster=-1 as outliers


@dataclass
class LLMConfig:
    """Configuration for LLM explanations."""

    model: str = "llama3.1:8b"
    host: str = "http://localhost:11434"
    temperature: float = 0.3
    max_tokens: int = 2000


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""

    categorical_columns: list[str] = field(default_factory=list)
    numerical_columns: list[str] = field(default_factory=list)
    id_column: Optional[str] = None
    exclude_columns: list[str] = field(default_factory=list)
    high_cardinality_threshold: int = 20


@dataclass
class Config:
    """Main configuration container."""

    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    outlier: OutlierConfig = field(default_factory=OutlierConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
