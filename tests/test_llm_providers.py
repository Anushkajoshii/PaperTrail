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


def ok_body(content='{"answer": "hi"}'):
    return httpx.Response(
        200, json={"model": "m", "choices": [{"message": {"content": content}}], "usage": {}}
    )


def test_openai_compat_falls_back_to_json_mode_when_schema_unsupported():
    payloads = []

    def handler(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        if payload["response_format"]["type"] == "json_schema":
            return httpx.Response(400, text="model does not support response format `json_schema`")
        return ok_body()

    provider = OpenAICompatProvider(http_client(handler), "https://x/v1", MODELS)
    assert generate_structured(provider, REQ).output.answer == "hi"
    assert generate_structured(provider, REQ).output.answer == "hi"
    # Second call goes straight to JSON mode: the model's limitation is remembered.
    assert [p["response_format"]["type"] for p in payloads] == [
        "json_schema",
        "json_object",
        "json_object",
    ]
    assert '"answer"' in payloads[1]["messages"][0]["content"]  # schema is in the prompt


def test_openai_compat_other_400_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, text="context too long")

    provider = OpenAICompatProvider(http_client(handler), "https://x/v1", MODELS)
    with pytest.raises(LLMError, match="HTTP 400"):
        provider.complete(REQ)
    assert len(calls) == 1


def test_openai_compat_waits_and_retries_when_rate_limited():
    responses = iter(
        [httpx.Response(429, headers={"retry-after": "3"}), httpx.Response(429), ok_body()]
    )
    waits = []
    provider = OpenAICompatProvider(
        http_client(lambda r: next(responses)), "https://x/v1", MODELS, sleep=waits.append
    )
    assert provider.complete(REQ).data == {"answer": "hi"}
    assert waits == [3.0, 4.0]


def test_openai_compat_gives_up_after_rate_limit_retries():
    provider = OpenAICompatProvider(
        http_client(lambda r: httpx.Response(429)),
        "https://x/v1",
        MODELS,
        max_rate_retries=1,
        sleep=lambda s: None,
    )
    with pytest.raises(LLMError, match="HTTP 429"):
        provider.complete(REQ)


def test_groq_preset_uses_free_models_and_low_reasoning_effort(monkeypatch):
    s = Settings(_env_file=None, llm_provider=LLMProvider.GROQ, groq_api_key="gsk_test_not_real")
    provider = get_provider(s)
    assert provider.name == "groq"
    assert provider._url == "https://api.groq.com/openai/v1/chat/completions"
    assert provider._models[Purpose.JUDGE] == "openai/gpt-oss-120b"
    assert provider._payload(REQ, "m", None)["reasoning_effort"] == "low"


def test_groq_needs_a_key():
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        get_provider(Settings(_env_file=None, llm_provider=LLMProvider.GROQ))


def test_rate_limit_retries_come_from_settings():
    s = Settings(
        _env_file=None,
        llm_provider=LLMProvider.GROQ,
        groq_api_key="gsk_x",
        llm_rate_limit_retries=6,
    )
    assert get_provider(s)._max_rate_retries == 6
    assert Settings(_env_file=None).llm_rate_limit_retries == 6


def test_too_large_requests_fail_fast_and_output_is_capped():
    calls, payloads = [], []

    def handler(request):
        calls.append(1)
        payloads.append(json.loads(request.content))
        return httpx.Response(429, text="Request too large for model on output tokens")

    provider = OpenAICompatProvider(
        http_client(handler), "https://x/v1", MODELS, max_output_tokens=4000, sleep=lambda s: None
    )
    with pytest.raises(LLMError, match="too large"):
        provider.complete(REQ)  # REQ asks for 8000 output tokens
    assert len(calls) == 1 and payloads[0]["max_tokens"] == 4000
    groq = get_provider(Settings(_env_file=None, llm_provider=LLMProvider.GROQ, groq_api_key="k"))
    assert groq._max_output_tokens == 4000
