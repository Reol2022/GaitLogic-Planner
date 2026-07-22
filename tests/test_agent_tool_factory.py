from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.schemas import AgentContext, AgentLimits, AgentRequest
from server.agent.tools.factory import COACH_AGENT_TOOL_NAMES, build_coach_agent_tool_registry
from tests.agent_tool_fakes import FakeDependencies, NOW


def context() -> AgentContext:
    request = AgentRequest(user_id=81, message="fictional", intent=AgentIntent.EXPLAIN_RUNNER_STATE)
    return AgentContext(request_id=request.request_id, user_id=81, intent=request.intent, current_time=NOW, timezone="Asia/Shanghai")


def test_factory_registers_exactly_eight_read_only_tools() -> None:
    registry = build_coach_agent_tool_registry(FakeDependencies(), limits=AgentLimits())
    definitions = registry.list_tools()
    assert {item.name for item in definitions} == COACH_AGENT_TOOL_NAMES
    assert all(item.read_only and not item.requires_confirmation for item in definitions)


def test_no_tool_accepts_user_id_argument() -> None:
    registry = build_coach_agent_tool_registry(FakeDependencies())
    for definition in registry.list_tools():
        assert "user_id" not in definition.input_schema.get("properties", {})
    result = registry.invoke("get_runner_state", {"user_id": 999}, context())
    assert result.status == AgentToolStatus.INVALID_ARGUMENTS


def test_registry_uses_context_identity_only() -> None:
    deps = FakeDependencies()
    registry = build_coach_agent_tool_registry(deps)
    result = registry.invoke("get_runner_state", {}, context())
    assert result.status == AgentToolStatus.SUCCEEDED
    assert deps.seen_user_ids == [81]
