from __future__ import annotations

from datetime import datetime, timezone

from server.observability.metrics import (
    InMemoryMetricsSink,
    MetricPoint,
    MetricsRecorder,
    MetricsTraceSink,
)
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer, SpanRecord


def _span(
    component: str,
    operation: str,
    *,
    status: str = "SUCCEEDED",
    duration_ms: float = 10.0,
    fallback: bool = False,
    metadata: dict | None = None,
) -> SpanRecord:
    now = datetime.now(timezone.utc)
    return SpanRecord(
        trace_id="private-trace-id",
        span_id="private-span-id",
        parent_span_id=None,
        component=component,
        operation=operation,
        start_time=now,
        end_time=now,
        duration_ms=duration_ms,
        status=status,
        fallback=fallback,
        metadata=metadata or {},
    )


def test_agent_and_latency_metrics_are_derived_from_completed_spans() -> None:
    sink = InMemoryMetricsSink()
    recorder = MetricsRecorder(sink)
    for latency in (10.0, 20.0, 30.0, 40.0):
        recorder.record_span(_span("coach_api", "query", duration_ms=latency))

    labels = {"component": "coach_api", "operation": "query", "status": "SUCCEEDED", "fallback": "false"}
    assert sink.counter("agent_request_count", labels=labels) == 4
    assert sink.counter("agent_success_count", labels=labels) == 4
    assert sink.percentile("agent_total_latency_ms", 50, labels=labels) == 20.0
    assert sink.percentile("agent_total_latency_ms", 95, labels=labels) == 40.0


def test_provider_metrics_reuse_failure_taxonomy_and_attempt_count() -> None:
    sink = InMemoryMetricsSink()
    recorder = MetricsRecorder(sink)
    recorder.record_span(
        _span(
            "provider",
            "generate",
            status="FAILED",
            metadata={
                "provider_kind": "chat",
                "attempt": 3,
                "failure_category": "PROVIDER_TIMEOUT",
                "prompt": "must-not-become-a-label",
            },
        )
    )
    labels = {
        "component": "provider",
        "operation": "generate",
        "status": "FAILED",
        "fallback": "false",
        "provider_kind": "chat",
        "failure_category": "PROVIDER_TIMEOUT",
    }
    assert sink.counter("provider_request_count", labels=labels) == 1
    assert sink.counter("provider_failure", labels=labels) == 1
    assert sink.counter("provider_attempts", labels=labels) == 3
    assert sink.counter("provider_retry_count", labels=labels) == 2
    assert sink.counter("provider_timeout_count", labels=labels) == 1
    assert all("prompt" not in dict(series[1]) for series in sink._counters)
    assert all("trace" not in dict(series[1]) for series in sink._counters)


def test_tool_rag_validator_fallback_and_adaptive_metrics_are_real_span_mappings() -> None:
    sink = InMemoryMetricsSink()
    recorder = MetricsRecorder(sink)
    recorder.record_span(_span("tool", "invoke", metadata={"tool_name": "get_runner_state"}))
    recorder.record_span(_span("knowledge", "retrieve", status="FAILED"))
    recorder.record_span(_span("validator", "validate_output", status="FAILED"))
    recorder.record_span(_span("fallback", "deterministic_coach_response", fallback=True))
    recorder.record_span(_span("langgraph", "weekly_review"))
    recorder.record_span(_span("approval", "approve_proposal"))
    recorder.record_span(_span("approval", "reject_proposal"))

    assert sink.counter("tool_call_count") == 1
    assert sink.counter("tool_success_count") == 1
    assert sink.counter("retrieval_failure") == 1
    assert sink.counter("validator_reject") == 1
    assert sink.counter("fallback_count") == 1
    assert sink.counter("weekly_review_success") == 1
    assert sink.counter("proposal_approve") == 1
    assert sink.counter("proposal_apply_success") == 1
    assert sink.counter("proposal_reject") == 1


def test_disabled_recorder_and_sink_failures_do_not_change_business_execution() -> None:
    sink = InMemoryMetricsSink()
    disabled = MetricsRecorder(sink, enabled=False)
    disabled.record_span(_span("coach_api", "query"))
    assert sink.counter("agent_request_count") == 0

    class BrokenSink:
        def record(self, point: MetricPoint) -> None:
            raise RuntimeError("metrics unavailable")

    tracer = SafeTracer(MetricsTraceSink(MetricsRecorder(BrokenSink())))
    handle = tracer.start_trace()
    with tracer.span(handle, component="coach_api", operation="query", root=True):
        value = "business result"
    assert value == "business result"


def test_fanout_isolates_failed_trace_side_channel() -> None:
    class BrokenTraceSink:
        def write(self, span: SpanRecord) -> None:
            raise RuntimeError("export unavailable")

    memory = InMemoryTraceSink()
    tracer = SafeTracer(FanoutTraceSink(BrokenTraceSink(), memory))
    with tracer.span(tracer.start_trace(), component="tool", operation="invoke", root=True):
        pass
    assert len(memory.spans) == 1


def test_in_memory_sink_rejects_unknown_metric_kind_and_bounds_latency_samples() -> None:
    sink = InMemoryMetricsSink(max_latency_samples=2)
    labels = (("component", "provider"),)
    sink.record(MetricPoint("provider_latency_ms", 1, labels, kind="latency"))
    sink.record(MetricPoint("provider_latency_ms", 2, labels, kind="latency"))
    sink.record(MetricPoint("provider_latency_ms", 3, labels, kind="latency"))
    assert sink.latency_count("provider_latency_ms", labels={"component": "provider"}) == 2
    assert sink.percentile("provider_latency_ms", 50, labels={"component": "provider"}) == 2
