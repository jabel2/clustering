"""LLM agent for generating outlier explanations via Ollama."""

import json
import re
from dataclasses import dataclass, field

import ollama

from .context import ExplanationContext


@dataclass
class OutlierAnalysis:
    """Structured analysis for a single outlier."""

    id: str
    why_outlier: str
    unusual_attributes: str
    risk_level: str
    recommended_action: str


@dataclass
class ExplanationResult:
    """Result from LLM explanation."""

    explanation: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    structured_analysis: list[OutlierAnalysis] = field(default_factory=list)


class ExplanationAgent:
    """Generate natural language explanations using local Ollama models."""

    def __init__(
        self,
        model: str = "gpt-oss:20b",
        host: str = "http://localhost:11434",
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ):
        """Initialize explanation agent.

        Args:
            model: Ollama model name (e.g., 'llama3.1:8b', 'mistral').
            host: Ollama server URL.
            temperature: Sampling temperature (lower = more focused).
            max_tokens: Maximum tokens in response.
        """
        self.model = model
        self.host = host
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = ollama.Client(host=host)

    def explain(self, context: ExplanationContext) -> ExplanationResult:
        """Generate explanation for outliers.

        Args:
            context: ExplanationContext with prompt and data.

        Returns:
            ExplanationResult with the LLM's explanation.

        Raises:
            ConnectionError: If Ollama is not running.
        """
        try:
            # Log prompt length for debugging
            prompt_len = len(context.prompt)

            response = self._client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data analyst specializing in anomaly detection. "
                            "You explain why certain records are outliers in clear, "
                            "actionable terms. Be concise and focus on the most "
                            "significant findings."
                        ),
                    },
                    {
                        "role": "user",
                        "content": context.prompt,
                    },
                ],
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )

            # Handle both dict and object response formats
            if hasattr(response, "message"):
                explanation = response.message.content if hasattr(response.message, "content") else str(response.message)
            elif isinstance(response, dict) and "message" in response:
                msg = response["message"]
                explanation = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            else:
                explanation = str(response)

            # Check for empty response
            if not explanation or not explanation.strip():
                explanation = (
                    f"*LLM returned empty response. This may be due to prompt length ({prompt_len} chars). "
                    f"Try reducing the number of outliers or using a model with larger context window.*"
                )

            # Extract token counts if available
            prompt_tokens = response.get("prompt_eval_count")
            completion_tokens = response.get("eval_count")

            # Parse structured analysis from JSON block
            structured_analysis = self._parse_structured_analysis(explanation)

            return ExplanationResult(
                explanation=explanation,
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                structured_analysis=structured_analysis,
            )

        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() or "refused" in error_msg.lower():
                raise ConnectionError(
                    f"Cannot connect to Ollama at {self.host}. "
                    "Make sure Ollama is running with 'ollama serve'."
                ) from e
            raise

    def _parse_structured_analysis(self, explanation: str) -> list[OutlierAnalysis]:
        """Extract structured JSON analysis from the LLM response.

        Args:
            explanation: Full LLM response text.

        Returns:
            List of OutlierAnalysis objects, empty if parsing fails.
        """
        try:
            # Find JSON block between ```json and ```
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", explanation)
            if not json_match:
                # Try without the json marker
                json_match = re.search(r"```\s*(\[[\s\S]*?\])\s*```", explanation)

            if not json_match:
                return []

            json_str = json_match.group(1).strip()
            data = json.loads(json_str)

            results = []
            for item in data:
                results.append(OutlierAnalysis(
                    id=str(item.get("id", "")),
                    why_outlier=str(item.get("why_outlier", "")),
                    unusual_attributes=str(item.get("unusual_attributes", "")),
                    risk_level=str(item.get("risk_level", "")),
                    recommended_action=str(item.get("recommended_action", "")),
                ))
            return results

        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    def check_connection(self) -> bool:
        """Check if Ollama is available and model is loaded.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            response = self._client.list()
            # Handle both dict and object response formats
            if hasattr(response, "models"):
                available = [m.model for m in response.models]
            else:
                available = [m["name"] for m in response.get("models", [])]

            # Check if our model is available (handle version suffixes)
            model_base = self.model.split(":")[0]
            for m in available:
                if m.startswith(model_base):
                    return True

            return False
        except Exception:
            return False

    def list_available_models(self) -> list[str]:
        """List available Ollama models.

        Returns:
            List of model names.
        """
        try:
            response = self._client.list()
            # Handle both dict and object response formats
            if hasattr(response, "models"):
                return [m.model for m in response.models]
            else:
                return [m["name"] for m in response.get("models", [])]
        except Exception:
            return []
