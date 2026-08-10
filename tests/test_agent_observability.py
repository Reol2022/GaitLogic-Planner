from __future__ import annotations

from pydantic import BaseModel

from server.agent.enums import AgentIntent, AgentRiskLevel, AgentRunStatus
from server.agent.gateway import MockAgentLLMGateway
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentModelOutput, AgentRequest, AgentToolInvocation
from server.agent.tool import AgentTool
from server.observability.tracing import InMemoryTraceSink, SafeTracer


class _MetricInput(BaseModel):
    value: int


class _MetricOutput(BaseModel):
    value: int


class _MetricTool(AgentTool):
    name = "read_fictional_metric"
    description = "Read one fictional metric."
    input_model = _MetricInput
    output_model = _MetricOutput
    allowed_intents = (AgentIntent.EXPLAIN_RUNNER_STATE,)

    def execute(self, arguments: _MetricInput, _context) -> _MetricOutput:
        return _MetricOutput(value=arguments.value)


def _request() -> AgentRequest:
    return AgentRequest(
        user_id=999,
        message="Private fictional runner question that must not reach a trace.",
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
    )


def test_disabled_tracer_writes_nothing_and_preserves_agent_result() -> None:
    registry = AgentToolRegistry()
    registry.register(_MetricTool())
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer="A safe fictional explanation.",
        risk_level=AgentRiskLevel.UNKNOWN,
    )
    agent = GaitLogicCoachAgent(
        gateway=MockAgentLLMGateway(output),
        registry=registry,
        tracer=SafeTracer(InMemoryTraceSink(), enabled=False),
    )
    assert agent.run(_request()).status == AgentRunStatus.SUCCEEDED


def test_agent_trace_has_root_validator_provider_and_nested_tool_spans() -> None:
    sink = InMemoryTraceSink()
    registry = AgentToolRegistry()
    registry.register(_MetricTool())
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                tool_calls=[
                    AgentToolInvocation(
                        tool_name="read_fictional_metric", arguments={"value": 4}
                    )
                ],
            ),
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                answer="The fictional metric is available.",
                risk_level=AgentRiskLevel.UNKNOWN,
            ),
        ]
    )
    result = GaitLogicCoachAgent(
        gateway=gateway,
        registry=registry,
        tracer=SafeTracer(sink),
    ).run(_request())

    assert result.status == AgentRunStatus.SUCCEEDED
    root = next(item for item in sink.spans if item.component == "agent" and item.operation == "request")
    assert root.parent_span_id is None
    assert any(item.component == "validator" for item in sink.spans)
    assert any(item.component == "provider" and item.operation == "generate" for item in sink.spans)
    tool = next(item for item in sink.spans if item.component == "tool")
    assert tool.parent_span_id == root.span_id
    assert tool.metadata["tool_name"] == "read_fictional_metric"
    assert tool.duration_ms >= 0
    serialized = str([item.metadata for item in sink.spans])
    assert "Private fictional runner question" not in serialized
    assert "999" not in serialized


def test_error_fallback_and_sensitive_metadata_are_safe() -> None:
    sink = InMemoryTraceSink()
    tracer = SafeTracer(sink)
    with tracer.request(component="coach_api", operation="query", metadata={"intent": "TODAY_RECOMMENDATION"}) as handle:
        with tracer.span(
            handle,
            component="fallback",
            operation="deterministic",
            metadata={
                "fallback_reason": "MODEL_UNAVAILABLE",
                "prompt": "private prompt",
                "user_id": 999,
            },
        ) as span:
            span.mark_fallback("MODEL_UNAVAILABLE")
        try:
            with tracer.span(handle, component="knowledge", operation="retrieve"):
                raise RuntimeError("private index detail")
        except RuntimeError:
            pass

    fallback = next(item for item in sink.spans if item.component == "fallback")
    failed = next(item for item in sink.spans if item.component == "knowledge")
    assert fallback.fallback is True
    assert fallback.metadata == {"fallback_reason": "MODEL_UNAVAILABLE"}
    assert failed.status == "FAILED"
    assert failed.error_code == "TRACE_OPERATION_FAILED"
    serialized = str([item.metadata for item in sink.spans]).lower()
    assert "prompt" not in serialized
    assert "user_id" not in serialized
    assert "private index detail" not in serialized


def test_sink_failure_does_not_change_request_completion() -> None:
    class _BrokenSink:
        def write(self, _span) -> None:
            raise RuntimeError("fictional exporter outage")

    tracer = SafeTracer(_BrokenSink())
    with tracer.request(component="coach_api", operation="query"):
        completed = True
    assert completed is True
