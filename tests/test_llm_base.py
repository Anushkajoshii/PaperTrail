import pytest
from pydantic import BaseModel, Field

from papertrail.config import LLMProvider, Settings
from papertrail.llm import (
    LLMError,
    LLMRequest,
    MockProvider,
    Purpose,
    RawResult,
    UsageLog,
    generate_structured,
    get_provider,
    model_for,
)
from papertrail.llm.pricing import estimate_cost_usd


class Answer(BaseModel):
    value: int = Field(ge=0)


def req(**kw) -> LLMRequest[Answer]:
    return LLMRequest(system="sys", user="user", output_model=Answer, **kw)


class ScriptedProvider:
    """Returns a fixed sequence of raw outputs; records feedback it receives."""

    name = "scripted"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.feedback: list[str | None] = []

    def complete(self, request, *, feedback=None):
        self.feedback.append(feedback)
        return RawResult(
            data=self.outputs.pop(0), model="claude-haiku-5-5", input_tokens=1000, output_tokens=200
        )


def test_mock_provider_uses_handler_and_tracks_usage():
    provider = MockProvider(handlers={Answer: lambda r: Answer(value=42)})
    log = UsageLog()
    result = generate_structured(provider, req(), usage_log=log)
    assert result.output.value == 42
    assert result.usage.provider == "mock"
    assert result.usage.cost_usd == 0.0
    assert len(log.calls) == 1 and log.total_tokens > 0


def test_mock_without_handler_raises_helpful_error():
    with pytest.raises(LookupError, match="register_mock_handler"):
        MockProvider(handlers={}).complete(
            LLMRequest(system="", user="", output_model=type("X", (BaseModel,), {}))
        )


def test_invalid_output_is_retried_with_feedback():
    provider = ScriptedProvider([{"value": -1}, {"value": 3}])
    result = generate_structured(provider, req())
    assert result.output.value == 3
    assert result.attempts == 2
    assert provider.feedback[0] is None
    assert "value" in provider.feedback[1] and "greater than or equal" in provider.feedback[1]


def test_gives_up_after_max_attempts():
    provider = ScriptedProvider([{"value": -1}, {"oops": 1}])
    with pytest.raises(LLMError, match="did not validate"):
        generate_structured(provider, req())


def test_cost_estimate_uses_known_prices_and_strips_prefixes():
    assert estimate_cost_usd("claude-haiku-5-5", 1_000_000, 0) == pytest.approx(0.10)
    assert estimate_cost_usd("anthropic.claude-opus-5-5", 0, 1_000_000) == pytest.approx(20.0)
    assert estimate_cost_usd("llama3.1", 10**6, 10**6) == 0.0
    log = UsageLog()
    generate_structured(ScriptedProvider([{"value": 1}]), req(), usage_log=log)
    assert log.total_cost_usd == pytest.approx((1000 * 0.10 + 200 * 0.50) / 1e6)


def test_model_for_defaults_and_overrides():
    mock = Settings(_env_file=None)
    assert model_for(Purpose.EXTRACT, mock) == "mock"
    s = Settings(_env_file=None, llm_provider=LLMProvider.ANTHROPIC)
    assert model_for(Purpose.EXTRACT, s) == "claude-haiku-5-5"
    assert model_for(Purpose.JUDGE, s) == "claude-opus-5-5"
    b = Settings(_env_file=None, llm_provider=LLMProvider.BEDROCK, judge_model="anthropic.x")
    assert model_for(Purpose.EXTRACT, b).startswith("anthropic.")
    assert model_for(Purpose.JUDGE, b) == "anthropic.x"
    with pytest.raises(ValueError, match="PAPERTRAIL_EXTRACT_MODEL"):
        model_for(Purpose.EXTRACT, Settings(_env_file=None, llm_provider=LLMProvider.OLLAMA))


def test_default_provider_is_mock():
    assert get_provider(Settings(_env_file=None)).name == "mock"
