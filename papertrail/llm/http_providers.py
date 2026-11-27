"""Optional non-Claude backends over plain HTTP: OpenAI-compatible endpoints and local Ollama.

These run free open models (Groq's free tier, or Ollama on a laptop) and make it easy to compare
them with Claude in the eval report. Both ask for JSON matching the Pydantic model's schema.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import httpx

from papertrail.config import Settings
from papertrail.llm.base import InvalidOutputError, LLMError, LLMRequest, Purpose, RawResult
from papertrail.llm.factory import model_for


def _messages(request: LLMRequest, feedback: str | None) -> list[dict[str, str]]:
    user = request.user if feedback is None else f"{request.user}\n\n{feedback}"
    return [{"role": "system", "content": request.system}, {"role": "user", "content": user}]


def _parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidOutputError("model returned invalid JSON", text) from exc
    if not isinstance(data, dict):
        raise InvalidOutputError("model returned JSON that is not an object", text)
    return data


def _post(
    client: httpx.Client,
    url: str,
    payload: dict,
    name: str,
    *,
    max_rate_retries: int = 0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """POST and return JSON. On 429 (rate limited), wait as the server asks and try again."""
    for attempt in range(max_rate_retries + 1):
        try:
            resp = client.post(url, json=payload)
            if resp.status_code == 429 and attempt < max_rate_retries:
                sleep(_retry_after(resp, attempt))
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"{name} HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"{name} connection error: {exc}") from exc
    raise AssertionError("unreachable")  # pragma: no cover


def _retry_after(resp: httpx.Response, attempt: int) -> float:
    try:
        wait = float(resp.headers.get("retry-after", ""))
    except ValueError:
        wait = 2.0 * 2**attempt
    return min(max(wait, 0.5), 60.0)


def _schema_unsupported(exc: LLMError) -> bool:
    text = str(exc).lower()
    return "http 400" in text and ("response_format" in text or "json_schema" in text)


class OpenAICompatProvider:
    """Any OpenAI-compatible chat API (Groq, Together, vLLM, ...).

    Asks for output matching the JSON schema. If the model does not support schemas, it falls
    back to plain JSON mode with the schema in the prompt; ``generate_structured`` still
    validates every answer and retries once with feedback.
    """

    name = "openai_compat"

    def __init__(
        self,
        client: httpx.Client,
        base_url: str,
        models: dict[Purpose, str],
        *,
        reasoning_effort: str | None = None,
        max_rate_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._models = models
        self._reasoning_effort = reasoning_effort
        self._max_rate_retries = max_rate_retries
        self._sleep = sleep
        self._json_object_models: set[str] = set()

    @classmethod
    def from_settings(cls, s: Settings) -> OpenAICompatProvider:
        if not s.openai_compat_base_url:
            raise LLMError("Set PAPERTRAIL_OPENAI_COMPAT_BASE_URL for provider 'openai_compat'")
        return cls._build(s, s.openai_compat_base_url, s.openai_compat_api_key)

    @classmethod
    def for_groq(cls, s: Settings) -> OpenAICompatProvider:
        if not s.groq_api_key:
            raise LLMError("Set PAPERTRAIL_GROQ_API_KEY for provider 'groq' (free at groq.com)")
        provider = cls._build(s, s.groq_base_url, s.groq_api_key, default_effort="low")
        provider.name = "groq"
        return provider

    @classmethod
    def _build(
        cls, s: Settings, base_url: str, key, default_effort: str | None = None
    ) -> OpenAICompatProvider:
        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key.get_secret_value()}"
        client = httpx.Client(headers=headers, timeout=s.llm_timeout_seconds)
        return cls(
            client,
            base_url,
            {p: model_for(p, s) for p in Purpose},
            reasoning_effort=s.reasoning_effort or default_effort,
        )

    def _payload(self, request: LLMRequest, model: str, feedback: str | None) -> dict:
        schema = request.output_model.model_json_schema()
        messages = _messages(request, feedback)
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": 0,
        }
        if model in self._json_object_models:
            messages[0] = {
                "role": "system",
                "content": f"{request.system}\n\nReply with one JSON object only, matching "
                f"this JSON schema:\n{json.dumps(schema)}",
            }
            payload["response_format"] = {"type": "json_object"}
        else:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.output_model.__name__,
                    "schema": schema,
                    "strict": False,
                },
            }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        return payload

    def _send(self, request: LLMRequest, model: str, feedback: str | None) -> dict:
        return _post(
            self._client,
            self._url,
            self._payload(request, model, feedback),
            self.name,
            max_rate_retries=self._max_rate_retries,
            sleep=self._sleep,
        )

    def complete(self, request: LLMRequest, *, feedback: str | None = None) -> RawResult:
        model = self._models[request.purpose]
        try:
            body = self._send(request, model, feedback)
        except LLMError as exc:
            if model in self._json_object_models or not _schema_unsupported(exc):
                raise
            self._json_object_models.add(model)  # remember: this model needs JSON mode
            body = self._send(request, model, feedback)
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.name}: unexpected response shape") from exc
        usage = body.get("usage") or {}
        return RawResult(
            data=_parse_json(text or ""),
            model=body.get("model", model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


class OllamaProvider:
    name = "ollama"

    def __init__(self, client: httpx.Client, base_url: str, models: dict[Purpose, str]) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/api/chat"
        self._models = models

    @classmethod
    def from_settings(cls, s: Settings) -> OllamaProvider:
        client = httpx.Client(timeout=s.llm_timeout_seconds)
        return cls(client, s.ollama_base_url, {p: model_for(p, s) for p in Purpose})

    def complete(self, request: LLMRequest, *, feedback: str | None = None) -> RawResult:
        model = self._models[request.purpose]
        body = _post(
            self._client,
            self._url,
            {
                "model": model,
                "messages": _messages(request, feedback),
                "format": request.output_model.model_json_schema(),
                "stream": False,
                "options": {"temperature": 0, "num_predict": request.max_tokens},
            },
            self.name,
        )
        text = (body.get("message") or {}).get("content", "")
        return RawResult(
            data=_parse_json(text),
            model=body.get("model", model),
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
        )
