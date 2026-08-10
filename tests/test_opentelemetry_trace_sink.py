from __future__ import annotations

from datetime import datetime, timezone

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from planner_core.config import Settings
from server.adaptive_workflow.graph import build_adaptive_approval_graph
from server.observability.factory import (
    TraceConfigurationError,
    build_configured_tracer,
    build_trace_sink,
)
from server.observability.sinks import (
    NoopTraceSink,
    OpenTelemetryTraceSink,
    OpenTelemetryUnavailableError,
)
from server.observability.tracing import InMemoryTraceSink, SafeTracer, SpanRecord


class _FakeStatusCode:
    OK = "OK"
    ERROR = "ERROR"


class _FakeStatus:
    def __init__(self, code, description=None) -> None:
        self.code = code
        self.description = description


class _FakeSpan:
    def __init__(self, name: str, kwargs: dict) -> None:
        self.name = name
        self.kwargs = kwargs
        self.status = None
        self.ended_at = None

    def set_attribute(self, key, value) -> None:
        self.kwargs.setdefault("attributes", {})[key] = value

    def set_status(self, status) -> None:
        self.status = status

    def end(self, end_time=None) -> None:
        self.ended_at = end_time


class _FakeTracer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.spans: list[_FakeSpan] = []

    def start_span(self, name: str, **kwargs):
        if self.fail:
            raise RuntimeError("fictional exporter failure")
        span = _FakeSpan(name, kwargs)
        self.spans.append(span)
        return span


class _FakeTraceApi:
    @staticmethod
    def set_span_in_context(span):
        return {"parent": span}


def _sink(*, fail: bool = False) -> tuple[OpenTelemetryTraceSink, _FakeTracer]:
    tracer = _FakeTracer(fail=fail)
    return (
        OpenTelemetryTraceSink.for_test(
            tracer=tracer,
            trace_api=_FakeTraceApi(),
            status_class=_FakeStatus,
            status_code=_FakeStatusCode,
        ),
        tracer,
    )


def test_noop_sink_and_disabled_tracing_are_safe_noops() -> None:
    sink = NoopTraceSink()
    tracer = SafeTracer(sink)
    with tracer.request(component="agent", operation="request"):
        completed = True
    assert completed is True
    assert tracer.enabled is True

    disabled = SafeTracer(sink, enabled=False)
    with disabled.request(component="agent", operation="request"):
        disabled_completed = True
    assert disabled_completed is True
    assert disabled.enabled is False


def test_otel_sink_buffers_child_completion_and_preserves_parent_relation() -> None:
    sink, fake = _sink()
    tracer = SafeTracer(sink)
    with tracer.request(component="coach_api", operation="query", metadata={"intent": "TODAY_RECOMMENDATION"}) as handle:
        with tracer.span(
            handle,
            component="validator",
            operation="validate_output",
            metadata={"validator_result": "VALID", "provider_status": "SUCCEEDED"},
        ):
            pass

    assert [item.name for item in fake.spans] == ["coach_api.query", "validator.validate_output"]
    root, child = fake.spans
    assert child.kwargs["context"] == {"parent": root}
    assert child.kwargs["attributes"]["gaitlogic.metadata.validator_result"] == "VALID"
    assert child.kwargs["attributes"]["gaitlogic.metadata.provider_status"] == "SUCCEEDED"
    assert root.status.code == "OK"
    assert child.ended_at is not None


def test_otel_sink_exports_safe_error_and_fallback_attributes_only() -> None:
    sink, fake = _sink()
    now = datetime.now(timezone.utc)
    sink.write(
        SpanRecord(
            trace_id="trace-a",
            span_id="root-a",
            parent_span_id=None,
            component="agent",
            operation="request",
            start_time=now,
            end_time=now,
            duration_ms=1.0,
            status="FAILED",
            error_code="AGENT_MODEL_FAILED",
            fallback=True,
            metadata={
                "fallback_reason": "MODEL_UNAVAILABLE",
                "prompt": "private prompt",
                "user_id": 9,
            },
        )
    )
    exported = fake.spans[0]
    attributes = exported.kwargs["attributes"]
    assert attributes["gaitlogic.fallback"] is True
    assert attributes["gaitlogic.error_code"] == "AGENT_MODEL_FAILED"
    assert attributes["gaitlogic.metadata.fallback_reason"] == "MODEL_UNAVAILABLE"
    assert "prompt" not in str(attributes)
    assert "user_id" not in str(attributes)
    assert exported.status.code == "ERROR"
    assert exported.status.description == "AGENT_MODEL_FAILED"


def test_exporter_failure_isolated_from_business_request(caplog) -> None:
    sink, _fake = _sink(fail=True)
    tracer = SafeTracer(sink)
    with tracer.request(component="coach_api", operation="query"):
        completed = True
    assert completed is True
    assert "fictional exporter failure" not in caplog.text


def test_configuration_is_disabled_by_default_and_rejects_unsafe_endpoint() -> None:
    disabled = Settings(_env_file=None)
    assert build_configured_tracer(disabled).enabled is False
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            AGENT_TRACING_ENABLED=True,
            AGENT_TRACE_EXPORTER="otlp",
            OTEL_EXPORTER_OTLP_ENDPOINT="https://token@example.test/v1/traces?secret=value",
        )


def test_invalid_or_unavailable_exporter_degrades_to_noop(monkeypatch) -> None:
    missing_endpoint = Settings(
        _env_file=None,
        AGENT_TRACING_ENABLED=True,
        AGENT_TRACE_EXPORTER="otlp",
    )
    with pytest.raises(TraceConfigurationError):
        build_trace_sink(missing_endpoint)

    configured = Settings(
        _env_file=None,
        AGENT_TRACING_ENABLED=True,
        AGENT_TRACE_EXPORTER="otlp",
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318/v1/traces",
    )
    monkeypatch.setattr(
        OpenTelemetryTraceSink,
        "from_otlp",
        classmethod(lambda cls, **kwargs: (_ for _ in ()).throw(OpenTelemetryUnavailableError("OTEL_SDK_UNAVAILABLE"))),
    )
    assert build_configured_tracer(configured).enabled is False


def test_hitl_resume_propagates_only_safe_internal_trace_context() -> None:
    sink = InMemoryTraceSink()
    graph = build_adaptive_approval_graph(
        checkpointer=InMemorySaver(),
        tracer=SafeTracer(sink),
    )
    config = {"configurable": {"thread_id": "fictional-trace-thread"}}
    paused = graph.invoke(
        {"user_id": 7, "proposal_id": 99, "decision": None},
        config,
    )
    assert "__interrupt__" in paused
    resumed = graph.invoke(Command(resume="approve"), config)
    assert resumed["decision"] == "approve"
    await_span, resume_span = sink.spans
    assert await_span.operation == "await_approval"
    assert resume_span.operation == "resume_approval"
    assert resume_span.trace_id == await_span.trace_id
    assert resume_span.parent_span_id == await_span.span_id
    assert "user_id" not in str([item.metadata for item in sink.spans])
