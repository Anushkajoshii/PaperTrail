import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from papertrail.config import LLMProvider, Settings
from papertrail.llm import LLMError, LLMRequest, Purpose, generate_structured, get_provider
from papertrail.llm.anthropic_provider import AnthropicProvider, BedrockProvider
from papertrail.llm.base import InvalidOutputError
from papertrail.llm.http_providers import OllamaProvider, OpenAICompatProvider


class Out(BaseModel):
    answer: str


REQ = LLMRequest(system="be precise", user="question", output_model=Out, purpose=Purpose.JUDGE)
MODELS = {Purpose.EXTRACT: "claude-haiku-5-5", Purpose.JUDGE: "claude-opus-5-5"}


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def anthropic_response(text, stop_reason="end_turn", model="claude-opus-5-5"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        stop_details=None,
        model=model,
        usage=SimpleNamespace(input_tokens=120, output_tokens=30),
    )


def fake_anthropic(*responses):
    messages = FakeMessages(responses)
    return SimpleNamespace(messages=messages), messages


# --- Anthropic / Bedrock -------------------------------------------------------------------


def test_anthropic_sends_structured_output_request_and_parses():
    client, messages = fake_anthropic(anthropic_response('{"answer": "42"}'))
    provider = AnthropicProvider(client, MODELS)
    result = generate_structured(provider, REQ)
    assert result.output.answer == "42"
    assert result.usage.input_tokens == 120
    assert result.usage.cost_usd > 0
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5-5"  # judge model chosen by purpose
    assert call["system"] == "be precise"
    assert call["output_config"]["effort"] == "medium"
    fmt = call["output_config"]["format"]
    assert fmt["type"] == "json_schema" and "answer" in fmt["schema"]["properties"]
    assert "thinking" not in call and "temperature" not in call


def test_anthropic_invalid_json_is_retried_with_feedback():
    client, messages = fake_anthropic(
        anthropic_response("not json"), anthropic_response('{"answer": "ok"}')
    )
    result = generate_structured(AnthropicProvider(client, MODELS), REQ)
    assert result.output.answer == "ok" and result.attempts == 2
    assert "not valid JSON" in messages.calls[1]["messages"][0]["content"]


@pytest.mark.parametrize(("stop", "msg"), [("refusal", "declined"), ("max_tokens", "cut off")])
def test_anthropic_refusal_and_truncation_raise(stop, msg):
    client, _ = fake_anthropic(anthropic_response("{}", stop_reason=stop))
    with pytest.raises(LLMError, match=msg):
        AnthropicProvider(client, MODELS).complete(REQ)


def test_bedrock_uses_prefixed_model_ids():
    client, messages = fake_anthropic(anthropic_response('{"answer": "x"}'))
    s = Settings(_env_file=None, llm_provider=LLMProvider.BEDROCK)
    from papertrail.llm import model_for

    provider = BedrockProvider(client, {p: model_for(p, s) for p in Purpose})
    provider.complete(REQ)
    assert messages.calls[0]["model"] == "anthropic.claude-opus-5-5"
    assert provider.name == "bedrock"


def test_anthropic_from_settings_builds_without_network(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    provider = get_provider(Settings(_env_file=None, llm_provider=LLMProvider.ANTHROPIC))
    assert provider.name == "anthropic"


# --- HTTP providers -------------------------------------------------------------------------


def http_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_compat_request_and_response():
    seen = {}

    def handler(request: httpx.Request):
        seen.update(json.loads(request.content))
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "model": "llama-3.3-70b",
                "choices": [{"message": {"content": '{"answer": "hi"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
        )

    provider = OpenAICompatProvider(
        http_client(handler), "https://api.example.com/v1/", {p: "llama-3.3-70b" for p in Purpose}
    )
    result = generate_structured(provider, REQ)
    assert result.output.answer == "hi" and result.usage.output_tokens == 3
    assert seen["url"] == "https://api.example.com/v1/chat/completions"
    assert seen["response_format"]["type"] == "json_schema"
    assert seen["messages"][0] == {"role": "system", "content": "be precise"}


def test_openai_compat_http_error_becomes_llm_error():
    provider = OpenAICompatProvider(
        http_client(lambda r: httpx.Response(401, text="bad key")), "https://x/v1", MODELS
    )
    with pytest.raises(LLMError, match="HTTP 401"):
        provider.complete(REQ)


def test_openai_compat_requires_base_url():
    with pytest.raises(LLMError, match="BASE_URL"):
        OpenAICompatProvider.from_settings(
            Settings(
                _env_file=None,
                llm_provider=LLMProvider.OPENAI_COMPAT,
                extract_model="m",
                judge_model="m",
            )
        )


def test_ollama_request_and_invalid_json():
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "llama3.1",
                "message": {"content": "[1, 2]"},
                "prompt_eval_count": 5,
                "eval_count": 2,
            },
        )

    provider = OllamaProvider(http_client(handler), "http://localhost:11434", MODELS)
    with pytest.raises(InvalidOutputError, match="not an object"):
        provider.complete(REQ)
    assert payloads[0]["stream"] is False
    assert payloads[0]["format"]["properties"]["answer"]["type"] == "string"
