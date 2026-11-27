"""Observability: a trace of every check (agent steps, AI calls, searches) with timing,
tokens and cost. Off by default; Langfuse when keys are set. See ADR-017."""

from papertrail.observability.tracing import (
    LangfuseTracer,
    MemoryTracer,
    NoopTracer,
    Tracer,
    current_tracer,
    get_tracer,
    record_generation,
    span,
    use_tracer,
)

__all__ = [
    "LangfuseTracer",
    "MemoryTracer",
    "NoopTracer",
    "Tracer",
    "current_tracer",
    "get_tracer",
    "record_generation",
    "span",
    "use_tracer",
]
