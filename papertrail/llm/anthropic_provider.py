"""Claude via the Anthropic API, and Claude on Amazon Bedrock.

Both use the official Anthropic Python SDK and native structured outputs
(``output_config.format`` with a JSON schema derived from the Pydantic model), so the model is
constrained to answer in the shape we ask for. We still validate with Pydantic afterwards, because
our models carry rules (e.g. "a supported verdict must cite evidence") that a JSON schema cannot
express.
"""

from __future__ import annotations

import json
from typing import Any

from papertrail.config import Settings
from papertrail.llm.base import InvalidOutputError, LLMError, LLMRequest, Purpose, RawResult
from papertrail.llm.factory import model_for

# Extraction is simple and high-volume, so it gets low effort. Judging needs more reasoning.
DEFAULT_EFFORT: dict[Purpose, str] = {Purpose.EXTRACT: "low", Purpose.JUDGE: "medium"}


class AnthropicProvider:
    """Claude through the Anthropic API (``ANTHROPIC_API_KEY`` or an ``ant auth login`` profile)."""

    name = "anthropic"

    def __init__(
        self,
        client: Any,
        models: dict[Purpose, str],
        effort: dict[Purpose, str] | None = None,
    ) -> None:
        self._client = client
        self._models = models
        self._effort = effort or DEFAULT_EFFORT

    @classmethod
    def from_settings(cls, s: Settings) -> AnthropicProvider:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise LLMError("Install the 'anthropic' extra: uv sync --extra anthropic") from exc
        client = anthropic.Anthropic(timeout=s.llm_timeout_seconds, max_retries=s.llm_max_retries)
        return cls(client, {p: model_for(p, s) for p in Purpose})

    def complete(self, request: LLMRequest, *, feedback: str | None = None) -> RawResult:
        import anthropic

        model = self._models[request.purpose]
        user = request.user if feedback is None else f"{request.user}\n\n{feedback}"
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": self._effort[request.purpose],
                    "format": {
                        "type": "json_schema",
                        "schema": anthropic.transform_schema(request.output_model),
                    },
                },
            )
        except anthropic.APIStatusError as exc:
            # The SDK has already retried 429/5xx. Anything left is a real failure.
            raise LLMError(f"{self.name} API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"{self.name} connection error: {exc}") from exc

        if response.stop_reason == "refusal":
            raise LLMError(f"{self.name} declined the request ({_refusal_category(response)})")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"{self.name} output was cut off at max_tokens={request.max_tokens}")

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidOutputError("model returned invalid JSON", text) from exc
        return RawResult(
            data=data,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


class BedrockProvider(AnthropicProvider):
    """Claude on Amazon Bedrock, using the SDK's Bedrock Mantle client and AWS credentials."""

    name = "bedrock"

    @classmethod
    def from_settings(cls, s: Settings) -> BedrockProvider:
        try:
            from anthropic import AnthropicBedrockMantle
        except ImportError as exc:  # pragma: no cover
            raise LLMError("Install the 'bedrock' extra: uv sync --extra bedrock") from exc
        client = AnthropicBedrockMantle(
            aws_region=s.bedrock_region or s.aws_region,
            timeout=s.llm_timeout_seconds,
            max_retries=s.llm_max_retries,
        )
        return cls(client, {p: model_for(p, s) for p in Purpose})


def _refusal_category(response: Any) -> str:
    details = getattr(response, "stop_details", None)
    return getattr(details, "category", None) or "no category given"
