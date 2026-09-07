from datetime import date

from server.agent.capabilities import ExecutionContext, execution_context_scope
from server.agent.enums import AgentIntent
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentContext, AgentToolResult
from server.agent.tool import AgentTool
from server.agent.skills import WeatherAwareTrainingSkill
from server.agent.tools.weather import GetWeatherTool, WeatherDataKind, WeatherSnapshot, WeatherToolInput
from pydantic import BaseModel


class _Empty(BaseModel):
    pass


class _Output(BaseModel):
    value: str = "ok"


class _FakeTool(AgentTool):
    name = "fake_capability"
    description = "test only"
    input_model = _Empty
    output_model = _Output
    allowed_intents = (AgentIntent.GENERAL_TRAINING_QUESTION,)
    def execute(self, arguments, context):
        return _Output()


def test_execution_context_reuses_same_successful_tool_result() -> None:
    registry = AgentToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    context = AgentContext.model_validate({"request_id": "00000000-0000-0000-0000-000000000001", "user_id": 1, "intent": "GENERAL_TRAINING_QUESTION", "current_time": "2026-01-01T00:00:00+00:00", "timezone": "UTC"})
    with execution_context_scope(ExecutionContext()):
        first = registry.invoke(tool.name, {}, context)
        second = registry.invoke(tool.name, {}, context)
    assert first.data == second.data


class _Weather:
    name = "fake"
    def get_weather(self, *, location_label, target_date, data_kind):
        return WeatherSnapshot(location_label=location_label, target_date=target_date, data_kind=data_kind, provider=self.name, temperature_c=33, humidity_percent=86)


def test_weather_tool_returns_facts_not_training_decision() -> None:
    tool = GetWeatherTool(_Weather())
    context = AgentContext.model_validate({"request_id": "00000000-0000-0000-0000-000000000001", "user_id": 1, "intent": "GENERAL_TRAINING_QUESTION", "current_time": "2026-01-01T00:00:00+00:00", "timezone": "UTC"})
    output = tool.execute(WeatherToolInput(location_label="Chengdu", target_date=date(2026, 1, 2), data_kind=WeatherDataKind.FORECAST), context)
    assert output.temperature_c == 33
    assert not hasattr(output, "recommendation")
