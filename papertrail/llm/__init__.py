"""Pluggable LLM layer: one typed interface, several backends, and an offline mock."""

from papertrail.llm.base import (
    LLMError,
    LLMRequest,
    LLMResult,
    Provider,
    Purpose,
    RawResult,
    Usage,
    UsageLog,
    generate_structured,
)
from papertrail.llm.factory import get_provider, model_for
from papertrail.llm.mock import MockProvider, register_mock_handler

__all__ = [
    "LLMError",
    "LLMRequest",
    "LLMResult",
    "MockProvider",
    "Provider",
    "Purpose",
    "RawResult",
    "Usage",
    "UsageLog",
    "generate_structured",
    "get_provider",
    "model_for",
    "register_mock_handler",
]
