"""Build the configured provider and pick the model for each pipeline step."""

from __future__ import annotations

from papertrail.config import LLMProvider, Settings, get_settings
from papertrail.llm.base import Provider, Purpose

# Default models per provider and step: a small fast model extracts, a stronger model judges.
DEFAULT_MODELS: dict[LLMProvider, dict[Purpose, str]] = {
    LLMProvider.ANTHROPIC: {Purpose.EXTRACT: "claude-haiku-5-5", Purpose.JUDGE: "claude-opus-5-5"},
    LLMProvider.BEDROCK: {
        Purpose.EXTRACT: "anthropic.claude-haiku-5-5",
        Purpose.JUDGE: "anthropic.claude-opus-5-5",
    },
    # Free tier, open-weight models with JSON-schema support on Groq.
    LLMProvider.GROQ: {Purpose.EXTRACT: "openai/gpt-oss-20b", Purpose.JUDGE: "openai/gpt-oss-120b"},
}


def model_for(purpose: Purpose, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    explicit = s.extract_model if purpose is Purpose.EXTRACT else s.judge_model
    if explicit:
        return explicit
    if s.llm_provider is LLMProvider.MOCK:
        return "mock"
    try:
        return DEFAULT_MODELS[s.llm_provider][purpose]
    except KeyError:
        raise ValueError(
            f"Set PAPERTRAIL_{purpose.upper()}_MODEL for provider '{s.llm_provider}'"
        ) from None


def get_provider(settings: Settings | None = None) -> Provider:
    s = settings or get_settings()
    match s.llm_provider:
        case LLMProvider.MOCK:
            from papertrail.llm.mock import MockProvider

            return MockProvider()
        case LLMProvider.ANTHROPIC:
            from papertrail.llm.anthropic_provider import AnthropicProvider

            return AnthropicProvider.from_settings(s)
        case LLMProvider.BEDROCK:
            from papertrail.llm.anthropic_provider import BedrockProvider

            return BedrockProvider.from_settings(s)
        case LLMProvider.OPENAI_COMPAT:
            from papertrail.llm.http_providers import OpenAICompatProvider

            return OpenAICompatProvider.from_settings(s)
        case LLMProvider.GROQ:
            from papertrail.llm.http_providers import OpenAICompatProvider

            return OpenAICompatProvider.for_groq(s)
        case LLMProvider.OLLAMA:
            from papertrail.llm.http_providers import OllamaProvider

            return OllamaProvider.from_settings(s)
    raise ValueError(f"Unknown provider {s.llm_provider}")  # pragma: no cover
