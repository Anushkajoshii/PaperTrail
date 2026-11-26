"""Deterministic, offline stand-in for an LLM.

Each pipeline step registers a *handler* for the output model it asks for: a plain Python
function that produces a plausible answer with simple rules. This keeps tests and CI fast, free
and repeatable, and lets the whole app run on a laptop with no keys.

The mock is NOT used to measure accuracy. Real-model evaluations do that (Parts 6 and 13).
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from papertrail.llm.base import LLMRequest, RawResult

MockHandler = Callable[[LLMRequest], BaseModel | dict]

_HANDLERS: dict[type[BaseModel], MockHandler] = {}


def register_mock_handler(output_model: type[BaseModel]) -> Callable[[MockHandler], MockHandler]:
    """Decorator: ``@register_mock_handler(MyOutput)`` above a ``fn(request) -> MyOutput``."""

    def decorator(fn: MockHandler) -> MockHandler:
        _HANDLERS[output_model] = fn
        return fn

    return decorator


class MockProvider:
    name = "mock"

    def __init__(self, handlers: dict[type[BaseModel], MockHandler] | None = None) -> None:
        # Explicit handlers (tests) take priority over globally registered ones.
        self._handlers = {**_HANDLERS, **(handlers or {})}

    def complete(self, request: LLMRequest, *, feedback: str | None = None) -> RawResult:
        handler = self._handlers.get(request.output_model)
        if handler is None:
            raise LookupError(
                f"No mock handler registered for {request.output_model.__name__}. "
                "Register one with @register_mock_handler."
            )
        out = handler(request)
        # Rough token estimate (about 4 characters per token) so cost and usage code paths run.
        approx_in = (len(request.system) + len(request.user)) // 4
        approx_out = len(out.model_dump_json() if isinstance(out, BaseModel) else str(out)) // 4
        return RawResult(data=out, model="mock", input_tokens=approx_in, output_tokens=approx_out)
