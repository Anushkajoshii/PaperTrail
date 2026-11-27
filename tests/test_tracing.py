import json

import httpx
import pytest
from pydantic import BaseModel, field_validator

from papertrail.agent.graph import run_check
from papertrail.config import Settings
from papertrail.llm import LLMError, LLMRequest, Purpose, generate_structured
from papertrail.llm.base import RawResult
from papertrail.observability import (
    LangfuseTracer,
    MemoryTracer,
    NoopTracer,
    get_tracer,
    record_generation,
    span,
    use_tracer,
)
from papertrail.observability.tracing import MAX_TEXT, Event
from tests.test_graph import deps, text_input


def test_a_check_is_one_trace_with_a_span_per_step_and_a_generation_per_ai_call():
    tracer = MemoryTracer()
    check = run_check(text_input("hinglish_reel.txt"), deps(tracer=tracer), check_id="chk_t1").check

    (trace,) = tracer.of_type("trace")
    assert trace.id == "chk_t1" and trace.output["status"] == "completed"
    assert trace.output["claims"] == len(check.claims)
    assert {e.trace_id for e in tracer.events} == {"chk_t1"}

    steps = {s.name: s for s in tracer.of_type("span") if s.parent_id is None}
    assert {"ingest", "extract", "registration", "research", "judge", "rulebook"} <= set(steps)
    research_ids = {s.id for s in tracer.of_type("span") if s.name == "research"}
    assert len(research_ids) == check.metrics.search_rounds  # one span per research round
    searches = [s for s in tracer.of_type("span") if s.name == "search"]
    assert searches and all(s.parent_id in research_ids for s in searches)

    gens = tracer.of_type("generation")
    assert len(gens) == check.metrics.llm_calls
    by_parent = {}
    for g in gens:
        by_parent.setdefault(g.parent_id, []).append(g)
    assert set(by_parent) <= {steps["extract"].id, steps["judge"].id, steps["rulebook"].id}
    assert by_parent[steps["judge"].id]
    assert all(g.name.startswith("judge: ") for g in by_parent[steps["judge"].id])
    assert all(g.name.startswith("extract: ") for g in by_parent[steps["extract"].id])
    assert all(g.usage["total"] >= 0 and g.model == "mock" for g in gens)


def test_metrics_record_provider_models_and_time_per_step():
    check = run_check(text_input("english_post.txt"), deps()).check
    m = check.metrics
    assert m.llm_provider == "mock"
    assert m.models == {"extract": "mock", "judge": "mock"}
    assert set(m.step_ms) >= {"ingest", "extract", "judge", "rulebook"}
    assert all(v >= 0 for v in m.step_ms.values())


def test_failed_checks_are_traced_with_the_error():
    tracer = MemoryTracer()
    bad = text_input("english_post.txt").model_copy(update={"text": "   "})
    check = run_check(bad, deps(tracer=tracer)).check
    assert check.status.value == "failed"
    (trace,) = tracer.of_type("trace")
    assert trace.output["status"] == "failed" and "empty" in trace.output["error"]
    ingest = next(s for s in tracer.of_type("span") if s.name == "ingest")
    assert ingest.level == "ERROR" and "IngestError" in ingest.status


class Answer(BaseModel):
    n: int

    @field_validator("n")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("must be positive")
        return v


class Flaky:
    name = "flaky"

    def __init__(self, answers):
        self.answers = list(answers)

    def complete(self, request, *, feedback=None):
        return RawResult(
            data={"n": self.answers.pop(0)}, model="m1", input_tokens=7, output_tokens=2
        )


def test_validation_retries_are_visible_as_warnings():
    tracer = MemoryTracer()
    req = LLMRequest(system="s", user="u", output_model=Answer, purpose=Purpose.JUDGE)
    with use_tracer(tracer, trace_id="t", name="x"):
        assert generate_structured(Flaky([-1, 3]), req).output.n == 3
    first, second = tracer.of_type("generation")
    assert first.level == "WARNING" and "positive" in first.status
    assert second.level == "DEFAULT" and second.metadata["attempt"] == 2
    assert "feedback" in second.input and second.usage == {"input": 7, "output": 2, "total": 9}
    with use_tracer(tracer, trace_id="t2", name="x"), pytest.raises(LLMError):
        generate_structured(Flaky([-1, -2]), req)


def test_without_a_trace_nothing_is_recorded_and_nothing_breaks():
    with span("orphan") as s:
        assert s is None
    record_generation(
        "x", model="m", input=1, output=2, input_tokens=0, output_tokens=0, latency_ms=1, cost_usd=0
    )
    tracer = NoopTracer()
    with use_tracer(tracer, trace_id="t", name="n"), span("inner") as s:
        assert s is None


def test_langfuse_batch_format_and_long_text_is_clipped():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(207, json={"successes": [], "errors": []})

    tracer = LangfuseTracer(
        "pk-lf-test",
        "sk-lf-test",
        "https://lf.example.test/",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        environment="test",
    )
    with use_tracer(tracer, trace_id="chk_1", name="check", tags=["mock"]), span("judge"):
        record_generation(
            "judge",
            model="m",
            input={"user": "x" * (MAX_TEXT + 500)},
            output={"ok": 1},
            input_tokens=10,
            output_tokens=5,
            latency_ms=12.5,
            cost_usd=0.001,
        )
    assert seen["url"] == "https://lf.example.test/api/public/ingestion"
    assert seen["auth"].startswith("Basic ")
    kinds = [e["type"] for e in seen["body"]["batch"]]
    assert kinds == ["generation-create", "span-create", "trace-create"]
    gen, sp, trace = (e["body"] for e in seen["body"]["batch"])
    assert gen["traceId"] == "chk_1" and gen["parentObservationId"] == sp["id"]
    assert gen["usageDetails"] == {"input": 10, "output": 5, "total": 15}
    assert gen["costDetails"] == {"total": 0.001} and gen["environment"] == "test"
    assert gen["input"]["user"].endswith(f"[{MAX_TEXT + 500} chars]")
    assert trace["id"] == "chk_1" and trace["tags"] == ["mock"]


@pytest.mark.parametrize(
    "response", [httpx.Response(401, text="bad key"), httpx.Response(207, json={"errors": [{}]})]
)
def test_langfuse_errors_never_break_a_check(response):
    tracer = LangfuseTracer(
        "pk", "sk", client=httpx.Client(transport=httpx.MockTransport(lambda r: response))
    )
    tracer.emit(Event(type="span", id="1", name="s", trace_id="t"))
    tracer.flush()  # logged, not raised

    def boom(request):
        raise httpx.ConnectError("offline")

    tracer = LangfuseTracer("pk", "sk", client=httpx.Client(transport=httpx.MockTransport(boom)))
    tracer.emit(Event(type="span", id="1", name="s", trace_id="t"))
    tracer.flush()
    tracer.flush()  # empty batch: no request


def test_get_tracer_needs_both_keys():
    assert isinstance(get_tracer(Settings(_env_file=None)), NoopTracer)
    assert isinstance(get_tracer(Settings(_env_file=None, langfuse_public_key="pk")), NoopTracer)
    t = get_tracer(Settings(_env_file=None, langfuse_public_key="pk", langfuse_secret_key="sk"))
    assert isinstance(t, LangfuseTracer)
