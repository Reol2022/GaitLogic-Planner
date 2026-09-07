from __future__ import annotations

import json

from planner_core.config import Settings
from server.observability.factory import build_trace_sink
from server.observability.metrics import InMemoryMetricsSink, MetricsRecorder
from server.observability.sinks import JsonlTraceSink
from server.observability.tracing import SafeTracer


def test_domain_schema_normalizes_legacy_spans_without_exporting_private_metadata() -> None:
    from server.observability.tracing import InMemoryTraceSink

    sink = InMemoryTraceSink()
    tracer = SafeTracer(sink)
    with tracer.request(component="coach_api", operation="query", metadata={"intent": "GENERAL"}) as handle:
        with tracer.span(
            handle,
            component="tool",
            operation="invoke",
            metadata={"tool_name": "get_runner_state", "prompt": "private", "user_id": 1},
        ):
            pass

    assert [item.domain_name for item in sink.spans] == ["tool.call", "coach.request"]
    assert sink.spans[0].metadata == {"tool_name": "get_runner_state"}


def test_local_jsonl_export_is_safe_and_factory_is_explicitly_configurable(tmp_path) -> None:
    path = tmp_path / "traces.jsonl"
    sink = JsonlTraceSink(path)
    tracer = SafeTracer(sink)
    with tracer.request(component="coach_api", operation="query", metadata={"intent": "GENERAL", "message": "private"}):
        pass

    line = json.loads(path.read_text(encoding="utf-8"))
    assert line["name"] == "coach.request"
    assert "message" not in str(line)
    assert "user_id" not in str(line)

    configured = Settings(
        _env_file=None,
        AGENT_TRACING_ENABLED=True,
        AGENT_TRACE_EXPORTER="local",
        AGENT_TRACE_LOCAL_PATH=str(path),
    )
    assert isinstance(build_trace_sink(configured), JsonlTraceSink)


def test_standard_domain_metrics_are_low_cardinality() -> None:
    from server.observability.tracing import InMemoryTraceSink

    trace_sink = InMemoryTraceSink()
    tracer = SafeTracer(trace_sink)
    with tracer.request(component="coach_api", operation="query", metadata={"intent": "GENERAL"}) as handle:
        with tracer.span(handle, component="tool", operation="invoke", metadata={"tool_name": "get_runner_state"}):
            pass
    metrics = InMemoryMetricsSink()
    recorder = MetricsRecorder(metrics)
    for span in trace_sink.spans:
        recorder.record_span(span)

    assert metrics.counter("gaitlogic.agent.requests") == 1
    assert metrics.counter("gaitlogic.tool.calls") == 1
    assert all("trace_id" not in dict(labels) for _, labels in metrics._counters)
