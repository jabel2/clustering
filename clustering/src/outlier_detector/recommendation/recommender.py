"""LLM-based settings recommender for outlier detection."""

import json
import re
from dataclasses import dataclass, field

import ollama

from .analyzer import DatasetProfile, DatasetAnalyzer


@dataclass
class RecommendedSettings:
    """Recommended settings from LLM analysis."""

    id_column: str | None = None
    categorical_columns: list[str] = field(default_factory=list)
    numerical_columns: list[str] = field(default_factory=list)
    exclude_columns: list[str] = field(default_factory=list)
    expected_outlier_pct: float | None = None
    auto_method: str = "heuristic"
    min_cluster_size: int | None = None
    column_weights: dict[str, float] = field(default_factory=dict)
    outlier_signals: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class RecommendationResult:
    """Result from LLM recommendation."""

    settings: RecommendedSettings
    raw_response: str
    model: str
    cli_command: str


class SettingsRecommender:
    """Use LLM to recommend outlier detection settings."""

    def __init__(
        self,
        model: str = "gpt-oss:20b",
        host: str = "http://localhost:11434",
        temperature: float = 0.1,
    ):
        """Initialize recommender.

        Args:
            model: Ollama model name.
            host: Ollama server URL.
            temperature: Sampling temperature.
        """
        self.model = model
        self.host = host
        self.temperature = temperature
        self._client = ollama.Client(host=host)

    def recommend(
        self,
        profile: DatasetProfile,
        domain_context: str = "",
        file_path: str = "",
    ) -> RecommendationResult:
        """Get LLM recommendations for settings.

        Args:
            profile: Dataset profile from analyzer.
            domain_context: Description of the domain/use case.
            file_path: Path to the data file (for CLI command).

        Returns:
            RecommendationResult with recommended settings.
        """
        # Build prompt
        prompt = self._build_prompt(profile, domain_context)

        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data science expert specializing in anomaly detection "
                            "and clustering. You help users configure outlier detection tools "
                            "by analyzing their datasets and recommending optimal settings. "
                            "Be specific and practical in your recommendations."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                options={
                    "temperature": self.temperature,
                    "num_predict": 2000,
                },
            )

            # Extract response text
            if hasattr(response, "message"):
                raw_response = (
                    response.message.content
                    if hasattr(response.message, "content")
                    else str(response.message)
                )
            elif isinstance(response, dict) and "message" in response:
                msg = response["message"]
                raw_response = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            else:
                raw_response = str(response)

            # Parse settings from response
            settings = self._parse_settings(raw_response, profile)

            # Build CLI command
            cli_command = self._build_cli_command(settings, file_path)

            return RecommendationResult(
                settings=settings,
                raw_response=raw_response,
                model=self.model,
                cli_command=cli_command,
            )

        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() or "refused" in error_msg.lower():
                raise ConnectionError(
                    f"Cannot connect to Ollama at {self.host}. "
                    "Make sure Ollama is running with 'ollama serve'."
                ) from e
            raise

    def _build_prompt(self, profile: DatasetProfile, domain_context: str) -> str:
        """Build the LLM prompt."""
        analyzer = DatasetAnalyzer()
        profile_text = analyzer.to_prompt_text(profile)

        prompt = f"""I'm configuring an outlier detection tool that uses HDBSCAN clustering to find anomalous records in a dataset. Please analyze this dataset and recommend settings.

## Dataset Profile
{profile_text}

"""
        if domain_context:
            prompt += f"""## Domain Context
{domain_context}

"""

        prompt += """## What I Need

Please analyze this dataset and provide recommendations in the following JSON format:

```json
{
  "id_column": "column_name or null",
  "categorical_columns": ["col1", "col2"],
  "numerical_columns": ["col3", "col4"],
  "exclude_columns": ["cols to exclude from analysis"],
  "expected_outlier_pct": 1.5,
  "auto_method": "heuristic|balanced|dbcv",
  "min_cluster_size": null,
  "column_weights": {"important_col": 2.0},
  "outlier_signals": ["Signal 1 to watch for", "Signal 2"],
  "reasoning": "Brief explanation of your recommendations"
}
```

Guidelines:
1. **id_column**: Identify which column is the unique identifier (should not be used for clustering)
2. **categorical_columns**: Columns that should be one-hot encoded (departments, titles, locations, etc.)
3. **numerical_columns**: Columns that should be scaled numerically (counts, amounts, dates as numbers)
4. **exclude_columns**: Columns that shouldn't be used (IDs, names, free text, timestamps)
5. **expected_outlier_pct**: Based on the domain, what % of records would you expect to be outliers? (typically 1-5% for most datasets)
6. **auto_method**:
   - "heuristic" (recommended for most cases) - uses log2(n) for min_cluster_size
   - "balanced" - optimizes for 5-15% outlier rate
   - "dbcv" - optimizes cluster quality (may find fewer outliers)
7. **column_weights**: Columns that are more important for detecting outliers should get higher weights (>1.0)
8. **outlier_signals**: What patterns in this data would indicate an anomaly? Be specific to the domain.

Provide your analysis and then the JSON block.
"""
        return prompt

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text for Windows console compatibility."""
        if not text:
            return text
        # Replace common Unicode characters that cause issues on Windows
        replacements = {
            '\u2011': '-',  # Non-breaking hyphen
            '\u2013': '-',  # En dash
            '\u2014': '--', # Em dash
            '\u2018': "'",  # Left single quote
            '\u2019': "'",  # Right single quote
            '\u201c': '"',  # Left double quote
            '\u201d': '"',  # Right double quote
            '\u2026': '...', # Ellipsis
            '\u00a0': ' ',  # Non-breaking space
            '\u202f': ' ',  # Narrow non-breaking space
            '\u2009': ' ',  # Thin space
            '\u200b': '',   # Zero-width space
            '\u2010': '-',  # Hyphen
            '\u2012': '-',  # Figure dash
            '\u2015': '--', # Horizontal bar
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        # Replace any remaining non-cp1252 characters with ?
        result = []
        for char in text:
            try:
                char.encode('cp1252')
                result.append(char)
            except UnicodeEncodeError:
                result.append('?')
        return ''.join(result)

    def _parse_settings(
        self, response: str, profile: DatasetProfile
    ) -> RecommendedSettings:
        """Parse recommended settings from LLM response."""
        settings = RecommendedSettings()

        try:
            # Find JSON block
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
            if not json_match:
                json_match = re.search(r"```\s*(\{[\s\S]*?\})\s*```", response)

            if json_match:
                json_str = json_match.group(1).strip()
                data = json.loads(json_str)

                settings.id_column = data.get("id_column")
                settings.categorical_columns = data.get("categorical_columns", [])
                settings.numerical_columns = data.get("numerical_columns", [])
                settings.exclude_columns = data.get("exclude_columns", [])
                settings.expected_outlier_pct = data.get("expected_outlier_pct")
                settings.auto_method = data.get("auto_method", "heuristic")
                settings.min_cluster_size = data.get("min_cluster_size")
                settings.column_weights = data.get("column_weights", {})
                # Sanitize text fields for Windows console compatibility
                settings.outlier_signals = [
                    self._sanitize_text(s) for s in data.get("outlier_signals", [])
                ]
                settings.reasoning = self._sanitize_text(data.get("reasoning", ""))

        except (json.JSONDecodeError, KeyError, TypeError):
            # If parsing fails, try to extract key info from text
            settings.reasoning = "Could not parse structured response. See raw output."

            # Try to find ID column from profile candidates
            if profile.id_column_candidates:
                settings.id_column = profile.id_column_candidates[0]

        return settings

    def _build_cli_command(self, settings: RecommendedSettings, file_path: str) -> str:
        """Build a CLI command from the recommended settings."""
        parts = ["python cli.py analyze"]

        if file_path:
            # Use relative path if possible
            if "clustering\\" in file_path:
                file_path = file_path.split("clustering\\")[-1].replace("\\", "/")
            parts.append(file_path)

        if settings.id_column:
            parts.append(f"--id-column {settings.id_column}")

        if settings.categorical_columns:
            parts.append(f'--categorical "{",".join(settings.categorical_columns)}"')

        if settings.numerical_columns:
            parts.append(f'--numerical "{",".join(settings.numerical_columns)}"')

        parts.append("--auto-cluster-size")
        parts.append(f"--auto-method {settings.auto_method}")

        return " \\\n  ".join(parts)

    def check_connection(self) -> bool:
        """Check if Ollama is available."""
        try:
            self._client.list()
            return True
        except Exception:
            return False
