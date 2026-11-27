"""The provider-neutral LLM interface.

Every LLM call in PaperTrail asks for a *typed* result: a Pydantic model. Providers turn that
into whatever their API needs (native structured output, JSON mode, ...), and
:func:`generate_structured` validates the result, retrying once with the validation error if the
model's output breaks a rule.

See docs/adr/002-pluggable-llm-with-offline-mock.md.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ValidationError

from papertrail.llm.pricing import estimate_cost_usd
from papertrail.observability.tracing import record_generation

log = logging.getLogger(__name__)


class Purpose(StrEnum):
    """Which pipeline step is calling. Each step can use a different model."""

    EXTRACT = "extract"
    JUDGE = "judge"


class LLMError(RuntimeError):
    """The provider failed (network, auth, refusal, or output that never validated)."""


class InvalidOutputError(LLMError):
    """The model answered, but not with parseable JSON. Retried like a validation error."""

    def __init__(self, message: str, raw_text: str = "") -> None:
        super().__init__(message)
        self.raw_text = raw_text


@dataclass(frozen=True)
class LLMRequest[T: BaseModel]:
    system: str
    user: str
    output_model: type[T]
    purpose: Purpose = Purpose.EXTRACT
    max_tokens: int = 8000


@dataclass(frozen=True)
class Usage:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    purpose: str = ""

    @property
    def cost_usd(self) -> float:
        return estimate_cost_usd(self.model, self.input_tokens, self.output_tokens)


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    output: T
    usage: Usage
    attempts: int = 1


@dataclass
class RawResult:
    """What a provider returns before validation: parsed JSON (dict) or a model instance."""

    data: dict | BaseModel
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    name: str

    def complete(self, request: LLMRequest, *, feedback: str | None = None) -> RawResult:
        """Run one call. ``feedback`` carries a validation error from a previous attempt."""
        ...


@dataclass
class UsageLog:
    """Collects usage across many calls, e.g. for one check (cost per check)."""

    calls: list[Usage] = field(default_factory=list)

    def add(self, usage: Usage) -> None:
        self.calls.append(usage)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(u.cost_usd for u in self.calls), 6)

    @property
    def total_tokens(self) -> int:
        return sum(u.input_tokens + u.output_tokens for u in self.calls)

    def models_by_purpose(self) -> dict[str, str]:
        """Which model did each step, e.g. {"extract": "openai/gpt-oss-20b", ...}."""
        return {u.purpose: u.model for u in self.calls if u.purpose}


def generate_structured[T: BaseModel](
    provider: Provider,
    request: LLMRequest[T],
    *,
    max_attempts: int = 2,
    usage_log: UsageLog | None = None,
) -> LLMResult[T]:
    """Call ``provider`` and return a validated ``request.output_model``.

    If the output fails validation (for example, a verdict that cites no evidence), the error is
    sent back to the model once so it can correct itself. After that we fail loudly rather than
    accept malformed data.
    """
    feedback: str | None = None
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        started = time.perf_counter()
        prompt = {"system": request.system, "user": request.user, "feedback": feedback}
        try:
            raw = provider.complete(request, feedback=feedback)
        except InvalidOutputError as exc:
            last_error = exc
            _trace_call(
                request,
                prompt,
                attempt,
                started,
                model="unknown",
                level="WARNING",
                status="Output was not valid JSON",
                output=exc.raw_text,
            )
            feedback = (
                "Your previous answer was not valid JSON. Answer again with only the JSON "
                "object that matches the required schema."
            )
            log.warning("LLM returned unparseable output (attempt %d)", attempt)
            continue
        usage = Usage(
            provider=provider.name,
            model=raw.model,
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            purpose=request.purpose.value,
        )
        if usage_log is not None:
            usage_log.add(usage)
        data = raw.data.model_dump() if isinstance(raw.data, BaseModel) else raw.data
        try:
            output = request.output_model.model_validate(data)
            _trace_call(request, prompt, attempt, started, usage=usage, output=data)
            return LLMResult(output=output, usage=usage, attempts=attempt)
        except ValidationError as exc:
            last_error = exc
            feedback = _feedback_for(exc)
            _trace_call(
                request,
                prompt,
                attempt,
                started,
                usage=usage,
                output=data,
                level="WARNING",
                status=f"Failed validation: {feedback[:300]}",
            )
            log.warning("LLM output failed validation (attempt %d): %s", attempt, feedback)
    raise LLMError(f"LLM output did not validate after {max_attempts} attempts: {last_error}")


def _trace_call(
    request: LLMRequest,
    prompt: dict,
    attempt: int,
    started: float,
    *,
    usage: Usage | None = None,
    model: str = "",
    output: object = None,
    level: str = "DEFAULT",
    status: str | None = None,
) -> None:
    """Record one AI call in the current trace (a no-op when tracing is off)."""
    record_generation(
        f"{request.purpose.value}: {request.output_model.__name__}",
        model=usage.model if usage else model,
        input={k: v for k, v in prompt.items() if v},
        output=output,
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
        latency_ms=usage.latency_ms if usage else round((time.perf_counter() - started) * 1000, 1),
        cost_usd=usage.cost_usd if usage else 0.0,
        level=level,
        status=status,
        metadata={
            "attempt": attempt,
            "provider": usage.provider if usage else "",
            "purpose": request.purpose.value,
        },
    )


def _feedback_for(exc: ValidationError) -> str:
    problems = [f"{'.'.join(map(str, e['loc'])) or '<root>'}: {e['msg']}" for e in exc.errors()]
    return (
        "Your previous answer did not match the required format. Fix these problems and answer "
        "again with the full corrected JSON:\n- " + "\n- ".join(problems[:10])
    )
