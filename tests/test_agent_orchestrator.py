from __future__ import annotations

from pydantic import BaseModel

from server.agent.enums import (
    AgentIntent,
    AgentRiskLevel,
    AgentRunStatus,
    AgentToolStatus,
    AgentTraceEventType,
)
from server.agent.errors import AgentErrorCode
from server.agent.gateway import MockAgentLLMGateway
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.providers.errors import AgentProviderError
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import (
    AgentLimits,
    AgentContext,
    AgentContextSeed,
    AgentModelOutput,
    AgentNotice,
    AgentRequest,
    AgentTodayRecommendation,
    AgentToolResult,
    AgentToolInvocation,
)
from server.agent.context import AgentContextBuilder
from server.agent.trace import AgentTrace
from server.agent.tool import AgentTool


class MetricInput(BaseModel):
    value: int


class MetricOutput(BaseModel):
    doubled: int


class MetricTool(AgentTool):
    name = "read_metric"
    description = "Read one fictional metric."
    input_model = MetricInput
    output_model = MetricOutput
    allowed_intents = (AgentIntent.EXPLAIN_RUNNER_STATE,)

    def execute(self, arguments: MetricInput, context: AgentContext) -> MetricOutput:
        return MetricOutput(doubled=arguments.value * 2)


class OtherMetricTool(MetricTool):
    name = "read_other_metric"


class ExplodingTool(MetricTool):
    name = "read_exploding_metric"

    def execute(self, arguments: MetricInput, context: AgentContext) -> MetricOutput:
        raise RuntimeError("private database detail")


def make_request(
    intent: AgentIntent = AgentIntent.EXPLAIN_RUNNER_STATE,
    message: str = "请解释完全虚构的训练状态。",
) -> AgentRequest:
    return AgentRequest(user_id=7001, message=message, intent=intent)


def make_registry(*tools: AgentTool) -> AgentToolRegistry:
    registry = AgentToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def direct_output(intent: AgentIntent = AgentIntent.EXPLAIN_RUNNER_STATE) -> AgentModelOutput:
    return AgentModelOutput(
        intent=intent,
        answer="这是基于完全虚构数据的解释。",
        risk_level=AgentRiskLevel.UNKNOWN,
    )


def test_unknown_intent_is_rejected_before_model_call() -> None:
    gateway = MockAgentLLMGateway([direct_output(AgentIntent.UNKNOWN)])
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request(AgentIntent.UNKNOWN))

    assert response.status == AgentRunStatus.REJECTED
    assert gateway.call_count == 0
    assert response.limitations[0].code == AgentErrorCode.AGENT_UNKNOWN_INTENT.value


def test_safe_direct_answer_uses_one_model_call() -> None:
    gateway = MockAgentLLMGateway(direct_output())
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.SUCCEEDED
    assert response.answer == "这是基于完全虚构数据的解释。"
    assert gateway.call_count == 1


def test_completed_context_tools_are_not_reoffered_to_model() -> None:
    request = make_request()
    initial_context = AgentContextBuilder().build(request)
    completed_context = initial_context.model_copy(
        update={
            "tool_results": [
                AgentToolResult(
                    tool_call_id=AgentToolInvocation(
                        tool_name="read_metric", arguments={"value": 1}
                    ).tool_call_id,
                    tool_name="read_metric",
                    status=AgentToolStatus.SUCCEEDED,
                    data={"doubled": 2},
                )
            ]
        }
    )


def today_output(answer: str) -> AgentModelOutput:
    return AgentModelOutput(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        answer=answer,
        summary="Fictional today summary.",
        risk_level=AgentRiskLevel.LOW,
        limitations=[AgentNotice(code="DEMO_LIMIT", message="Fictional limitation.")],
        today_recommendation=AgentTodayRecommendation(
            decision="PROCEED",
            planned_workout_status="PLANNED",
            headline="Proceed with the existing plan.",
            key_evidence=["distance_7d_km"],
            data_quality="AVAILABLE",
        ),
    )
    gateway = MockAgentLLMGateway(direct_output())
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
    )

    agent._call_model_untraced(
        request=request,
        context=completed_context,
        trace=AgentTrace(request_id=request.request_id),
    )

    assert gateway.exposed_tool_names == [[]]


def test_today_never_offers_model_initiated_tools() -> None:
    request = make_request(AgentIntent.TODAY_RECOMMENDATION)
    context = AgentContextBuilder().build(request)
    gateway = MockAgentLLMGateway(direct_output(AgentIntent.TODAY_RECOMMENDATION))
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
    )

    agent._call_model_untraced(
        request=request,
        context=context,
        trace=AgentTrace(request_id=request.request_id),
    )

    assert gateway.exposed_tool_names == [[]]


def test_fully_preloaded_explain_never_offers_additional_tools() -> None:
    request = make_request(AgentIntent.EXPLAIN_RUNNER_STATE)
    context = AgentContextBuilder().build(request).model_copy(
        update={
            "tool_results": [
                AgentToolResult(
                    tool_call_id=AgentToolInvocation(
                        tool_name=name,
                        arguments={},
                    ).tool_call_id,
                    tool_name=name,
                    status=AgentToolStatus.SUCCEEDED,
                    data={},
                )
                for name in (
                    "get_runner_state",
                    "get_runner_state_history",
                    "get_training_data_quality",
                )
            ]
        }
    )
    gateway = MockAgentLLMGateway(direct_output())
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
    )

    agent._call_model_untraced(
        request=request,
        context=context,
        trace=AgentTrace(request_id=request.request_id),
    )

    assert gateway.exposed_tool_names == [[]]


def test_explain_retries_validator_rejected_narrative_without_tools() -> None:
    request = make_request(AgentIntent.EXPLAIN_RUNNER_STATE)
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                answer="The model invented 83.67 km.",
            ),
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                answer="The current state follows the supplied evidence.",
            ),
        ]
    )
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(request)

    assert response.status == AgentRunStatus.SUCCEEDED
    assert gateway.call_count == 2
    assert gateway.exposed_tool_names == [[], []]
    assert "83.67" not in (response.answer or "")


def test_today_retries_only_a_validator_rejected_narrative_without_tools() -> None:
    request = make_request(AgentIntent.TODAY_RECOMMENDATION)
    gateway = MockAgentLLMGateway(
        [
            today_output("This is absolutely safe."),
            today_output("Proceed with the existing plan and monitor the supplied facts."),
        ]
    )
    agent = GaitLogicCoachAgent(gateway=gateway)
    seed = AgentContextSeed(
        today_workout={"workout_status": "PLANNED"},
        today_evaluation={
            "data_status": "AVAILABLE",
            "decision": "passed",
            "risk_level": "LOW",
            "evidence": ["distance_7d_km"],
        },
        data_quality={"data_status": "AVAILABLE"},
        limitations=[AgentNotice(code="DEMO_LIMIT", message="Fictional limitation.")],
    )

    response = agent.run(request, context_seed=seed)

    assert response.status == AgentRunStatus.SUCCEEDED
    assert gateway.call_count == 2
    assert gateway.exposed_tool_names == [[], []]


def test_tool_augmented_answer_uses_exactly_two_model_calls() -> None:
    call = AgentToolInvocation(tool_name="read_metric", arguments={"value": 4})
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(intent=AgentIntent.EXPLAIN_RUNNER_STATE, tool_calls=[call]),
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                answer="虚构指标的两倍是 8。",
                used_tool_call_ids=[call.tool_call_id],
            ),
        ]
    )
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
    )

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.SUCCEEDED
    assert gateway.call_count == 2
    assert response.tool_calls[0].status == AgentToolStatus.SUCCEEDED
    assert agent.last_context is not None
    assert agent.last_context.tool_results[0].data == {"doubled": 8}
    assert agent.last_trace is not None
    assert AgentTraceEventType.TOOL_CALL in {
        event.event_type for event in agent.last_trace.events
    }


def test_multiple_tools_execute_once_each_before_final_answer() -> None:
    calls = [
        AgentToolInvocation(tool_name="read_metric", arguments={"value": 2}),
        AgentToolInvocation(tool_name="read_other_metric", arguments={"value": 3}),
    ]
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(intent=AgentIntent.EXPLAIN_RUNNER_STATE, tool_calls=calls),
            direct_output(),
        ]
    )
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool(), OtherMetricTool()),
    )

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.SUCCEEDED
    assert [item.tool_name for item in response.tool_calls] == [
        "read_metric",
        "read_other_metric",
    ]


def test_same_tool_repetition_limit_rejects_without_executing_tools() -> None:
    calls = [
        AgentToolInvocation(tool_name="read_metric", arguments={"value": value})
        for value in (1, 2, 3)
    ]
    gateway = MockAgentLLMGateway(
        AgentModelOutput(intent=AgentIntent.EXPLAIN_RUNNER_STATE, tool_calls=calls)
    )
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
    )

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.REJECTED
    assert gateway.call_count == 1
    assert response.tool_calls == []
    assert response.limitations[0].code == AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED.value


def test_one_model_call_configuration_rejects_tool_loop() -> None:
    gateway = MockAgentLLMGateway(
        AgentModelOutput(
            intent=AgentIntent.EXPLAIN_RUNNER_STATE,
            tool_calls=[AgentToolInvocation(tool_name="read_metric", arguments={"value": 1})],
        )
    )
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
        limits=AgentLimits(max_model_calls=1),
    )

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.REJECTED
    assert gateway.call_count == 1


def test_second_model_call_cannot_request_more_tools() -> None:
    first_call = AgentToolInvocation(tool_name="read_metric", arguments={"value": 1})
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                tool_calls=[first_call],
            ),
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                answer="虚构回答",
                tool_calls=[
                    AgentToolInvocation(tool_name="read_metric", arguments={"value": 2})
                ],
            ),
        ]
    )
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
    )

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.VALIDATION_FAILED
    assert gateway.call_count == 2


def test_unknown_tool_is_rejected_without_execution() -> None:
    gateway = MockAgentLLMGateway(
        AgentModelOutput(
            intent=AgentIntent.EXPLAIN_RUNNER_STATE,
            tool_calls=[AgentToolInvocation(tool_name="not_registered", arguments={})],
        )
    )
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.VALIDATION_FAILED
    assert response.limitations[0].code == AgentErrorCode.AGENT_TOOL_NOT_FOUND.value


def test_total_tool_limit_is_enforced() -> None:
    calls = [
        AgentToolInvocation(tool_name="read_metric", arguments={"value": value})
        for value in (1, 2, 3)
    ]
    gateway = MockAgentLLMGateway(
        AgentModelOutput(intent=AgentIntent.EXPLAIN_RUNNER_STATE, tool_calls=calls)
    )
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
        limits=AgentLimits(max_tool_calls=2, max_same_tool_calls=3),
    )

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.VALIDATION_FAILED
    assert response.limitations[0].code == AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED.value


def test_tool_failure_is_safe_non_crashing_degradation() -> None:
    call = AgentToolInvocation(tool_name="read_exploding_metric", arguments={"value": 4})
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(intent=AgentIntent.EXPLAIN_RUNNER_STATE, tool_calls=[call]),
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                answer="工具数据不可用，只能说明当前限制。",
            ),
        ]
    )
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(ExplodingTool()),
    )

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.TOOL_FAILED
    assert response.tool_calls[0].safe_error_code == AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED
    assert response.limitations
    assert "private database detail" not in response.model_dump_json()


def test_gateway_exception_becomes_safe_model_failure() -> None:
    gateway = MockAgentLLMGateway([], error=TimeoutError("private upstream detail"))
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.MODEL_FAILED
    assert "private upstream detail" not in response.model_dump_json()
    assert response.limitations[0].code == AgentErrorCode.AGENT_MODEL_FAILED.value


def test_provider_error_preserves_its_safe_category() -> None:
    gateway = MockAgentLLMGateway(
        [],
        error=AgentProviderError(AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE),
    )
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.MODEL_FAILED
    assert response.limitations[0].code == AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE.value


def test_invalid_model_mapping_becomes_validation_failure() -> None:
    gateway = MockAgentLLMGateway({"answer": "missing intent"})
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.VALIDATION_FAILED
    assert response.limitations[0].code == AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID.value


def test_tools_are_exposed_only_for_matching_intent() -> None:
    gateway = MockAgentLLMGateway(direct_output(AgentIntent.GENERAL_TRAINING_QUESTION))
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=make_registry(MetricTool()),
    )

    response = agent.run(make_request(AgentIntent.GENERAL_TRAINING_QUESTION))

    assert response.status == AgentRunStatus.SUCCEEDED
    assert gateway.exposed_tool_names == [[]]


def test_trace_contains_only_safe_metadata() -> None:
    private_message = "我的虚构问题含 secret-user-text"
    gateway = MockAgentLLMGateway(direct_output())
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request(message=private_message))

    assert agent.last_trace is not None
    serialized = agent.last_trace.model_dump_json()
    assert "secret-user-text" not in serialized
    assert "7001" not in serialized
    assert response.trace_id == agent.last_trace.trace_id
    event_types = {item.event_type for item in agent.last_trace.events}
    assert {
        AgentTraceEventType.REQUEST_VALIDATED,
        AgentTraceEventType.CONTEXT_BUILT,
        AgentTraceEventType.MODEL_CALL,
        AgentTraceEventType.RESPONSE_VALIDATED,
        AgentTraceEventType.RUN_COMPLETED,
    }.issubset(event_types)


def test_validator_rejection_is_returned_as_structured_status() -> None:
    gateway = MockAgentLLMGateway(
        AgentModelOutput(
            intent=AgentIntent.EXPLAIN_RUNNER_STATE,
            answer="我已经为你修改正式训练计划。",
        )
    )
    agent = GaitLogicCoachAgent(gateway=gateway)

    response = agent.run(make_request())

    assert response.status == AgentRunStatus.VALIDATION_FAILED
    assert response.answer is None
    assert "修改正式训练计划" not in response.model_dump_json()
    assert response.limitations[0].code == AgentErrorCode.AGENT_TOOL_NOT_ALLOWED.value


def test_orchestrator_has_no_provider_specific_configuration() -> None:
    agent = GaitLogicCoachAgent(gateway=MockAgentLLMGateway(direct_output()))

    forbidden = {"api_key", "model", "temperature", "base_url"}

    assert not forbidden.intersection(vars(agent))
