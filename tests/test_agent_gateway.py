from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from server.agent.enums import AgentIntent, AgentRiskLevel
from server.agent.gateway import AgentLLMGateway, MockAgentLLMGateway
from server.agent.schemas import AgentContext, AgentModelOutput
from server.agent.trace import AgentTrace


def make_context() -> AgentContext:
    return AgentContext(
        request_id="27e04a9f-a388-4ff8-b5c6-b0e622fc39b8",
        user_id=7001,
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        current_time=datetime(2026, 8, 1, tzinfo=ZoneInfo("Asia/Shanghai")),
        timezone="Asia/Shanghai",
    )


def call_gateway(gateway: MockAgentLLMGateway) -> AgentModelOutput:
    context = make_context()
    return gateway.generate(
        system_instructions="safe internal instructions",
        user_message="虚构问题",
        context=context,
        tools=[],
        trace=AgentTrace(request_id=context.request_id),
    )


def test_gateway_is_abstract_provider_neutral_contract() -> None:
    with pytest.raises(TypeError):
        AgentLLMGateway()


def test_mock_gateway_returns_deterministic_sequence() -> None:
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(
                intent=AgentIntent.GENERAL_TRAINING_QUESTION,
                answer="第一条虚构回答",
                risk_level=AgentRiskLevel.UNKNOWN,
            ),
            {
                "intent": "GENERAL_TRAINING_QUESTION",
                "answer": "第二条虚构回答",
                "risk_level": "UNKNOWN",
            },
        ]
    )

    assert call_gateway(gateway).answer == "第一条虚构回答"
    assert call_gateway(gateway).answer == "第二条虚构回答"
    assert gateway.call_count == 2


def test_mock_gateway_validates_mapping_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access is forbidden in Mock gateway tests")

    monkeypatch.setattr("socket.create_connection", fail_network)
    gateway = MockAgentLLMGateway(
        {"intent": "GENERAL_TRAINING_QUESTION", "answer": "虚构回答"}
    )

    output = call_gateway(gateway)

    assert isinstance(output, AgentModelOutput)
    assert output.risk_level == AgentRiskLevel.UNKNOWN


def test_mock_gateway_rejects_invalid_structured_output() -> None:
    gateway = MockAgentLLMGateway({"answer": "missing required intent"})

    with pytest.raises(ValidationError):
        call_gateway(gateway)


def test_mock_gateway_can_simulate_failure_without_network() -> None:
    gateway = MockAgentLLMGateway([], error=TimeoutError("private upstream detail"))

    with pytest.raises(TimeoutError):
        call_gateway(gateway)


def test_mock_gateway_fails_when_output_queue_is_exhausted() -> None:
    gateway = MockAgentLLMGateway([])

    with pytest.raises(RuntimeError, match="output exhausted"):
        call_gateway(gateway)
