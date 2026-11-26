"""Optional non-Claude backends over plain HTTP: OpenAI-compatible endpoints and local Ollama.

These make it easy to compare open models (e.g. Llama via Groq, or Ollama on a laptop) against
Claude in the eval report. Both ask for JSON that matches the Pydantic model's JSON schema.
"""

from __future__ import annotations

import json

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


def _post(client: httpx.Client, url: str, payload: dict, name: str) -> dict:
    try:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise LLMError(
            f"{name} HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"{name} connection error: {exc}") from exc


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, client: httpx.Client, base_url: str, models: dict[Purpose, str]) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._models = models

    @classmethod
    def from_settings(cls, s: Settings) -> OpenAICompatProvider:
        if not s.openai_compat_base_url:
            raise LLMError("Set PAPERTRAIL_OPENAI_COMPAT_BASE_URL for provider 'openai_compat'")
        headers = {}
        if s.openai_compat_api_key:
            headers["Authorization"] = f"Bearer {s.openai_compat_api_key.get_secret_value()}"
        client = httpx.Client(headers=headers, timeout=s.llm_timeout_seconds)
        return cls(client, s.openai_compat_base_url, {p: model_for(p, s) for p in Purpose})

    def complete(self, request: LLMRequest, *, feedback: str | None = None) -> RawResult:
        model = self._models[request.purpose]
        body = _post(
            self._client,
            self._url,
            {
                "model": model,
                "messages": _messages(request, feedback),
                "max_tokens": request.max_tokens,
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": request.output_model.__name__,
                        "schema": request.output_model.model_json_schema(),
                    },
                },
            },
            self.name,
        )
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.name}: unexpected response shape") from exc
        usage = body.get("usage") or {}
        return RawResult(
            data=_parse_json(text),
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
