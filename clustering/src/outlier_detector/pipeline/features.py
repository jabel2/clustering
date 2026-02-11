"""Feature engineering for clustering preparation."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, OneHotEncoder


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""

    categorical_columns: list[str] = field(default_factory=list)
    numerical_columns: list[str] = field(default_factory=list)
    high_cardinality_threshold: int = 20


@dataclass
class FeatureResult:
    """Result of feature engineering."""

    features: np.ndarray
    feature_names: list[str]
    categorical_columns: list[str]
    numerical_columns: list[str]
    encoders: dict


def engineer_features(
    df: pd.DataFrame,
    config: FeatureConfig | None = None,
) -> FeatureResult:
    """Transform DataFrame into feature matrix for clustering.

    Args:
        df: Cleaned DataFrame.
        config: Feature engineering configuration. If None, auto-detects types.

    Returns:
        FeatureResult with transformed features and metadata.
    """
    config = config or FeatureConfig()

    # Auto-detect column types if not specified
    categorical_cols, numerical_cols = _detect_column_types(df, config)

    # Encode categorical features
    categorical_features, categorical_names, cat_encoder = _encode_categorical(
        df, categorical_cols, config.high_cardinality_threshold
    )

    # Scale numerical features
    numerical_features, numerical_names, num_scaler = _scale_numerical(
        df, numerical_cols
    )

    # Combine features
    all_features = []
    all_names = []

    if categorical_features is not None:
        all_features.append(categorical_features)
        all_names.extend(categorical_names)

    if numerical_features is not None:
        all_features.append(numerical_features)
        all_names.extend(numerical_names)

    if not all_features:
        raise ValueError("No features to process. Check your column configuration.")

    combined = np.hstack(all_features)

    return FeatureResult(
        features=combined,
        feature_names=all_names,
        categorical_columns=categorical_cols,
        numerical_columns=numerical_cols,
        encoders={"categorical": cat_encoder, "numerical": num_scaler},
    )


def _detect_column_types(
    df: pd.DataFrame, config: FeatureConfig
) -> tuple[list[str], list[str]]:
    """Detect categorical and numerical columns."""
    # Use config if provided
    if config.categorical_columns and config.numerical_columns:
        return config.categorical_columns, config.numerical_columns

    categorical = list(config.categorical_columns) if config.categorical_columns else []
    numerical = list(config.numerical_columns) if config.numerical_columns else []

    specified = set(categorical) | set(numerical)

    for col in df.columns:
        if col in specified:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            # Check if it's actually categorical (few unique values)
            unique_ratio = df[col].nunique() / len(df)
            if unique_ratio < 0.05 and df[col].nunique() < 10:
                categorical.append(col)
            else:
                numerical.append(col)
        else:
            categorical.append(col)

    return categorical, numerical


def _encode_categorical(
    df: pd.DataFrame,
    columns: list[str],
    high_cardinality_threshold: int,
) -> tuple[np.ndarray | None, list[str], OneHotEncoder | None]:
    """Encode categorical columns using one-hot encoding."""
    if not columns:
        return None, [], None

    # Filter to columns that exist
    columns = [c for c in columns if c in df.columns]
    if not columns:
        return None, [], None

    # For high cardinality columns, limit categories
    df_cat = df[columns].copy()
    for col in columns:
        if df_cat[col].nunique() > high_cardinality_threshold:
            # Keep top N-1 categories, group rest as 'Other'
            top_cats = df_cat[col].value_counts().head(high_cardinality_threshold - 1).index
            df_cat[col] = df_cat[col].apply(
                lambda x: x if x in top_cats else "_OTHER_"
            )

    # Convert all to string for consistent encoding
    df_cat = df_cat.astype(str)

    encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    encoded = encoder.fit_transform(df_cat)

    # Generate feature names
    feature_names = []
    for i, col in enumerate(columns):
        for cat in encoder.categories_[i]:
            feature_names.append(f"{col}_{cat}")

    return encoded, feature_names, encoder


def _scale_numerical(
    df: pd.DataFrame,
    columns: list[str],
) -> tuple[np.ndarray | None, list[str], RobustScaler | None]:
    """Scale numerical columns using RobustScaler."""
    if not columns:
        return None, [], None

    # Filter to columns that exist
    columns = [c for c in columns if c in df.columns]
    if not columns:
        return None, [], None

    scaler = RobustScaler()
    scaled = scaler.fit_transform(df[columns].values)

    return scaled, columns, scaler
