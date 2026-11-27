"""Tracing for one check: a tree of spans (agent steps, searches) and generations (AI calls).

Code anywhere in the pipeline calls :func:`span` or :func:`record_generation`; the tracer for
the current check is found through a context variable, so nothing has to be passed around.

* :class:`NoopTracer` (default): records nothing, costs nothing.
* :class:`MemoryTracer`: keeps events in memory (tests, and the local `--trace` CLI flag).
* :class:`LangfuseTracer`: sends events to Langfuse (free cloud tier or self-hosted) through
  its public ingestion API in one batch per check, flushed before a Lambda returns.

Tracing must never break a check: every export error is logged and swallowed.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

log = logging.getLogger(__name__)

MAX_TEXT = 4000  # characters kept per input/output field: enough to debug, bounded in size


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _clip(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + f"... [{len(value)} chars]"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value[:50]]
    return value


@dataclass
class Event:
    type: str  # trace | span | generation
    id: str
    name: str
    trace_id: str
    parent_id: str | None = None
    start: str = field(default_factory=_now)
    end: str | None = None
    input: Any = None
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    level: str = "DEFAULT"  # DEFAULT | WARNING | ERROR
    status: str | None = None
    model: str | None = None
    usage: dict[str, int] | None = None
    cost_usd: float | None = None
    tags: list[str] = field(default_factory=list)


class Tracer(Protocol):
    enabled: bool

    def emit(self, event: Event) -> None: ...
    def flush(self) -> None: ...


class NoopTracer:
    enabled = False

    def emit(self, event: Event) -> None:
        pass

    def flush(self) -> None:
        pass


class MemoryTracer:
    enabled = True

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass

    def of_type(self, kind: str) -> list[Event]:
        return [e for e in self.events if e.type == kind]


class LangfuseTracer:
    """Batches events and posts them to ``{host}/api/public/ingestion`` on flush."""

    enabled = True

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str = "https://cloud.langfuse.com",
        *,
        client: httpx.Client | None = None,
        environment: str = "local",
        release: str | None = None,
    ) -> None:
        self._url = host.rstrip("/") + "/api/public/ingestion"
        self._client = client or httpx.Client(timeout=10.0)
        self._auth = (public_key, secret_key)
        self._environment = environment
        self._release = release
        self._batch: list[dict] = []

    def emit(self, event: Event) -> None:
        self._batch.append(self._to_ingestion(event))

    def _to_ingestion(self, e: Event) -> dict:
        body: dict[str, Any] = {
            "id": e.id,
            "name": e.name,
            "input": _clip(e.input),
            "output": _clip(e.output),
            "metadata": _clip(e.metadata) or None,
            "environment": self._environment,
        }
        if e.type == "trace":
            body |= {"timestamp": e.start, "tags": e.tags, "release": self._release}
            kind = "trace-create"
        else:
            body |= {
                "traceId": e.trace_id,
                "parentObservationId": e.parent_id,
                "startTime": e.start,
                "endTime": e.end,
                "level": e.level,
                "statusMessage": e.status,
            }
            kind = "span-create"
            if e.type == "generation":
                kind = "generation-create"
                body["model"] = e.model
                if e.usage:
                    body["usageDetails"] = e.usage
                if e.cost_usd is not None:
                    body["costDetails"] = {"total": e.cost_usd}
        body = {k: v for k, v in body.items() if v is not None}
        return {"id": uuid.uuid4().hex, "type": kind, "timestamp": _now(), "body": body}

    def flush(self) -> None:
        batch, self._batch = self._batch, []
        if not batch:
            return
        try:
            resp = self._client.post(self._url, json={"batch": batch}, auth=self._auth)
            if resp.status_code >= 300 and resp.status_code != 207:
                log.warning("Langfuse rejected traces: HTTP %s", resp.status_code)
            elif resp.status_code == 207 and resp.json().get("errors"):
                log.warning("Langfuse rejected %d trace event(s)", len(resp.json()["errors"]))
        except Exception as exc:  # never let tracing break a check
            log.warning("Could not send traces to Langfuse: %s", exc)


# -- context -------------------------------------------------------------------------------

_NOOP = NoopTracer()
_tracer: contextvars.ContextVar[Tracer | None] = contextvars.ContextVar("tracer", default=None)
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_parent: contextvars.ContextVar[str | None] = contextvars.ContextVar("parent", default=None)


def current_tracer() -> Tracer:
    return _tracer.get() or _NOOP


@contextlib.contextmanager
def use_tracer(
    tracer: Tracer,
    *,
    trace_id: str,
    name: str,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Iterator[Event]:
    """Start a trace for one check. Events are flushed when the block ends (even on error)."""
    root = Event(
        type="trace",
        id=trace_id,
        name=name,
        trace_id=trace_id,
        input=input,
        metadata=metadata or {},
        tags=tags or [],
    )
    tokens = (_tracer.set(tracer), _trace_id.set(trace_id), _parent.set(None))
    try:
        yield root  # callers may set root.output before the block ends
    finally:
        root.end = _now()
        tracer.emit(root)
        tracer.flush()
        _parent.reset(tokens[2])
        _trace_id.reset(tokens[1])
        _tracer.reset(tokens[0])


@contextlib.contextmanager
def span(name: str, *, input: Any = None, metadata: dict[str, Any] | None = None):
    """Time a step. Exceptions are recorded (level ERROR) and re-raised."""
    tracer, trace_id = current_tracer(), _trace_id.get()
    if not tracer.enabled or trace_id is None:
        yield None
        return
    event = Event(
        type="span",
        id=uuid.uuid4().hex,
        name=name,
        trace_id=trace_id,
        parent_id=_parent.get(),
        input=input,
        metadata=dict(metadata or {}),
    )
    started = time.perf_counter()
    token = _parent.set(event.id)
    try:
        yield event
    except Exception as exc:
        event.level, event.status = "ERROR", f"{type(exc).__name__}: {exc}"[:500]
        raise
    finally:
        _parent.reset(token)
        event.end = _now()
        event.metadata["duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
        tracer.emit(event)


def record_generation(
    name: str,
    *,
    model: str,
    input: Any,
    output: Any,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    cost_usd: float,
    level: str = "DEFAULT",
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record one finished AI call under the current span."""
    tracer, trace_id = current_tracer(), _trace_id.get()
    if not tracer.enabled or trace_id is None:
        return
    end = datetime.now(UTC)
    start = datetime.fromtimestamp(end.timestamp() - latency_ms / 1000, UTC)
    tracer.emit(
        Event(
            type="generation",
            id=uuid.uuid4().hex,
            name=name,
            trace_id=trace_id,
            parent_id=_parent.get(),
            start=start.isoformat(),
            end=end.isoformat(),
            input=input,
            output=output,
            model=model,
            usage={
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            cost_usd=cost_usd,
            level=level,
            status=status,
            metadata={"latency_ms": latency_ms, **(metadata or {})},
        )
    )


def get_tracer(settings) -> Tracer:
    """Langfuse when both keys are set, otherwise no tracing."""
    pk, sk = settings.langfuse_public_key, settings.langfuse_secret_key
    if pk and sk:
        from papertrail import __version__

        return LangfuseTracer(
            pk.get_secret_value(),
            sk.get_secret_value(),
            settings.langfuse_host,
            environment=settings.env.value,
            release=__version__,
        )
    return NoopTracer()
