from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel, ConfigDict

from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.errors import AgentErrorCode, AgentToolRegistrationError
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentContext
from server.agent.tool import AgentTool


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


class ToolOutput(BaseModel):
    doubled: int


class ReadOnlyTool(AgentTool):
    name = "read_metric"
    description = "Read one fictional metric."
    input_model = ToolInput
    output_model = ToolOutput
    allowed_intents = (AgentIntent.EXPLAIN_RUNNER_STATE,)

    def execute(self, arguments: ToolInput, context: AgentContext) -> ToolOutput:
        return ToolOutput(doubled=arguments.value * 2)


class FailingTool(ReadOnlyTool):
    name = "failing_metric"

    def execute(self, arguments: ToolInput, context: AgentContext) -> ToolOutput:
        raise RuntimeError("secret provider detail")


class InvalidOutputTool(ReadOnlyTool):
    name = "invalid_output"

    def execute(self, arguments: ToolInput, context: AgentContext) -> dict:
        return {"wrong": arguments.value}


class NonSerializableOutput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    payload: object


class NonSerializableTool(ReadOnlyTool):
    name = "non_serializable_output"
    output_model = NonSerializableOutput

    def execute(self, arguments: ToolInput, context: AgentContext) -> NonSerializableOutput:
        return NonSerializableOutput(payload=object())


class WriteTool(ReadOnlyTool):
    name = "write_plan"
    read_only = False


def make_context(intent: AgentIntent = AgentIntent.EXPLAIN_RUNNER_STATE) -> AgentContext:
    return AgentContext(
        request_id="5ef6ac0d-b831-455c-bdf5-664af0f59a50",
        user_id=7001,
        intent=intent,
        current_time=datetime(2026, 8, 1, tzinfo=ZoneInfo("Asia/Shanghai")),
        timezone="Asia/Shanghai",
    )


def test_registry_accepts_only_explicit_agent_tools() -> None:
    registry = AgentToolRegistry()

    with pytest.raises(TypeError, match="only AgentTool"):
        registry.register(object())


def test_registry_rejects_duplicate_names() -> None:
    registry = AgentToolRegistry()
    registry.register(ReadOnlyTool())

    with pytest.raises(AgentToolRegistrationError) as exc_info:
        registry.register(ReadOnlyTool())

    assert exc_info.value.code == AgentErrorCode.AGENT_INTERNAL_ERROR


def test_registry_filters_tool_definitions_by_intent() -> None:
    registry = AgentToolRegistry()
    registry.register(ReadOnlyTool())

    assert [item.name for item in registry.list_tools(AgentIntent.EXPLAIN_RUNNER_STATE)] == [
        "read_metric"
    ]
    assert registry.list_tools(AgentIntent.WEEKLY_REVIEW) == []
    assert registry.get("read_metric") is not None
    assert registry.get("read_metric").definition.read_only is True


def test_registry_validates_input_and_output_on_success() -> None:
    registry = AgentToolRegistry()
    registry.register(ReadOnlyTool())

    result = registry.invoke("read_metric", {"value": 4}, make_context())

    assert result.status == AgentToolStatus.SUCCEEDED
    assert result.data == {"doubled": 8}


def test_registry_returns_safe_unknown_tool_error() -> None:
    result = AgentToolRegistry().invoke("missing_tool", {}, make_context())

    assert result.status == AgentToolStatus.NOT_FOUND
    assert result.safe_error_code == AgentErrorCode.AGENT_TOOL_NOT_FOUND


def test_registry_rejects_invalid_arguments() -> None:
    registry = AgentToolRegistry()
    registry.register(ReadOnlyTool())

    result = registry.invoke("read_metric", {"value": "not-an-int"}, make_context())

    assert result.status == AgentToolStatus.INVALID_ARGUMENTS
    assert result.safe_error_code == AgentErrorCode.AGENT_TOOL_ARGUMENTS_INVALID


@pytest.mark.parametrize(
    ("tool", "intent"),
    [(ReadOnlyTool(), AgentIntent.WEEKLY_REVIEW), (WriteTool(), AgentIntent.EXPLAIN_RUNNER_STATE)],
)
def test_registry_enforces_intent_and_read_only_boundaries(
    tool: AgentTool,
    intent: AgentIntent,
) -> None:
    registry = AgentToolRegistry()
    registry.register(tool)

    result = registry.invoke(tool.name, {"value": 2}, make_context(intent))

    assert result.status == AgentToolStatus.NOT_ALLOWED
    assert result.safe_error_code == AgentErrorCode.AGENT_TOOL_NOT_ALLOWED


@pytest.mark.parametrize(
    "tool",
    [FailingTool(), InvalidOutputTool(), NonSerializableTool()],
)
def test_registry_hides_tool_exception_and_invalid_output(tool: AgentTool) -> None:
    registry = AgentToolRegistry()
    registry.register(tool)

    result = registry.invoke(tool.name, {"value": 2}, make_context())

    assert result.status == AgentToolStatus.FAILED
    assert result.safe_error_code == AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED
    assert "secret provider detail" not in result.model_dump_json()
