from types import SimpleNamespace

from server.agent.enums import AgentIntent, AgentTraceEventType
from server.agent.schemas import AgentLimits, AgentRequest
from server.agent.tools.factory import build_coach_agent_tool_registry
from server.agent.training_context_builder import AgentTrainingContextBuilder
from server.agent.trace import AgentTrace
from tests.agent_tool_fakes import FakeDependencies, NOW


def build(intent: AgentIntent, deps: FakeDependencies | None = None, *, limits: AgentLimits | None = None):
    dependencies = deps or FakeDependencies()
    limits = limits or AgentLimits()
    registry = build_coach_agent_tool_registry(dependencies, limits=limits)
    builder = AgentTrainingContextBuilder(registry=registry, clock=lambda: NOW, limits=limits)
    request = AgentRequest(user_id=91, message="fictional", intent=intent)
    trace = AgentTrace(request_id=request.request_id)
    return builder.build(request, trace=trace), trace


def completed_tools(trace: AgentTrace) -> list[str]:
    return [
        event.tool_name
        for event in trace.events
        if event.event_type == AgentTraceEventType.CONTEXT_TOOL_COMPLETED
    ]


def test_today_preloads_minimum_tool_set() -> None:
    context, trace = build(AgentIntent.TODAY_RECOMMENDATION)
    assert completed_tools(trace) == [
        "get_runner_state", "get_today_workout", "get_recent_training",
        "get_training_data_quality", "evaluate_today_workout",
    ]
    assert context.runner_state is not None
    assert context.today_workout is not None


def test_weekly_and_explain_preload_different_bounded_sets() -> None:
    weekly, weekly_trace = build(AgentIntent.WEEKLY_REVIEW)
    explain, explain_trace = build(AgentIntent.EXPLAIN_RUNNER_STATE)
    assert completed_tools(weekly_trace) == [
        "get_runner_state", "get_runner_state_history", "get_recent_training",
        "get_current_training_cycle", "get_training_data_quality",
    ]
    assert completed_tools(explain_trace) == [
        "get_runner_state", "get_runner_state_history", "get_training_data_quality"
    ]
    assert weekly.recent_training is not None
    assert explain.recent_training is None


def test_general_is_minimal_and_unknown_loads_no_training_data() -> None:
    general, general_trace = build(AgentIntent.GENERAL_TRAINING_QUESTION)
    unknown, unknown_trace = build(AgentIntent.UNKNOWN)
    assert completed_tools(general_trace) == ["get_training_rules"]
    assert completed_tools(unknown_trace) == []
    assert unknown.runner_state is None
    assert unknown.tool_results == []


def test_one_tool_failure_degrades_with_missing_reason() -> None:
    deps = FakeDependencies()

    def fail(_user_id: int):
        raise RuntimeError("private database detail")

    setattr(deps, "current_runner_state", fail)
    context, trace = build(AgentIntent.EXPLAIN_RUNNER_STATE, deps)
    assert context.runner_state is None
    assert context.missing_reasons["get_runner_state"] == "AGENT_TOOL_EXECUTION_FAILED"
    assert len(completed_tools(trace)) == 3


def test_context_trimming_is_deterministic_and_reported() -> None:
    deps = FakeDependencies()
    deps.rules = [
        SimpleNamespace(
            code=f"RULE_{index}", name=f"Rule {index}", category="general",
            description="x" * 300, severity="info", evidence_refs_json=["metric"] * 10,
        )
        for index in range(30)
    ]
    limits = AgentLimits(max_context_chars=5000, max_rule_items=20)
    first, _ = build(AgentIntent.GENERAL_TRAINING_QUESTION, deps, limits=limits)
    second, _ = build(AgentIntent.GENERAL_TRAINING_QUESTION, deps, limits=limits)
    first_dump = first.model_dump(mode="json", exclude={"request_id", "tool_results"})
    second_dump = second.model_dump(mode="json", exclude={"request_id", "tool_results"})
    assert first_dump == second_dump
    assert any(item.code == "CONTEXT_TRIMMED" for item in first.limitations)


def test_context_is_json_serializable() -> None:
    context, _ = build(AgentIntent.TODAY_RECOMMENDATION)
    assert context.model_dump_json()
