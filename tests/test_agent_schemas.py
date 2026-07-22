from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from server.agent.context import AgentContextBuilder
from server.agent.enums import AgentIntent, AgentRiskLevel, AgentRunStatus
from server.agent.schemas import (
    AgentConversationMessage,
    AgentLimits,
    AgentModelOutput,
    AgentRequest,
    AgentResponse,
    AgentToolInvocation,
)


def test_agent_request_builds_server_owned_identity_and_request_id() -> None:
    request = AgentRequest.for_authenticated_user(
        user_id=7001,
        message="请解释今天的虚构训练状态。",
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
    )

    assert request.user_id == 7001
    assert request.request_id is not None
    assert request.intent == AgentIntent.EXPLAIN_RUNNER_STATE


def test_agent_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentRequest.model_validate(
            {
                "user_id": 7001,
                "message": "虚构问题",
                "intent": "GENERAL_TRAINING_QUESTION",
                "api_key": "must-not-be-accepted",
            }
        )


def test_agent_request_rejects_oversized_message() -> None:
    with pytest.raises(ValidationError):
        AgentRequest(
            user_id=7001,
            message="x" * 4001,
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        )


def test_agent_request_rejects_empty_message_and_invalid_intent() -> None:
    with pytest.raises(ValidationError):
        AgentRequest(user_id=7001, message="", intent=AgentIntent.UNKNOWN)
    with pytest.raises(ValidationError):
        AgentRequest.model_validate(
            {"user_id": 7001, "message": "虚构问题", "intent": "NOT_AN_INTENT"}
        )


def test_agent_request_rejects_oversized_conversation() -> None:
    messages = [
        AgentConversationMessage(role="user", content="x" * 1000)
        for _ in range(13)
    ]
    with pytest.raises(ValidationError, match="conversation context is too large"):
        AgentRequest(
            user_id=7001,
            message="虚构问题",
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
            conversation_context=messages,
        )


def test_context_builder_creates_json_only_timezone_aware_context() -> None:
    builder = AgentContextBuilder(
        clock=lambda: datetime(2026, 8, 1, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    request = AgentRequest(
        user_id=7001,
        message="解释状态",
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        conversation_context=[
            AgentConversationMessage(role="user", content="上一条虚构消息")
        ],
    )
    seed = builder.create_seed(
        runner_state={"fatigue_state": "UNKNOWN"},
        data_quality={"data_quality_level": "LOW"},
        missing_reasons={"rpe": "覆盖不足"},
    )

    context = builder.build(request, seed)

    assert context.current_time.utcoffset() is not None
    assert context.timezone == "Asia/Shanghai"
    assert context.runner_state == {"fatigue_state": "UNKNOWN"}
    assert context.conversation_context[0].content == "上一条虚构消息"
    assert isinstance(context.model_dump(mode="json"), dict)


def test_context_builder_rejects_non_json_domain_data() -> None:
    builder = AgentContextBuilder()

    with pytest.raises(ValueError, match="JSON-compatible"):
        builder.create_seed(runner_state={"unsafe": object()})


def test_context_builder_rejects_oversized_domain_data() -> None:
    builder = AgentContextBuilder()

    with pytest.raises(ValueError, match="too large"):
        builder.create_seed(runner_state={"summary": "x" * 50001})


def test_model_output_requires_unique_uuid_tool_call_ids() -> None:
    invocation = AgentToolInvocation(tool_name="read_metric", arguments={})

    with pytest.raises(ValidationError, match="tool_call_id must be unique"):
        AgentModelOutput(
            intent=AgentIntent.EXPLAIN_RUNNER_STATE,
            tool_calls=[invocation, invocation],
        )


def test_agent_limits_enforce_two_model_call_hard_cap() -> None:
    with pytest.raises(ValidationError):
        AgentLimits(max_model_calls=3)


def test_public_agent_response_has_no_identity_prompt_or_exception_fields() -> None:
    request = AgentRequest(
        user_id=7001,
        message="虚构问题",
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
    )
    response = AgentResponse(
        request_id=request.request_id,
        status=AgentRunStatus.SUCCEEDED,
        intent=request.intent,
        answer="这是完全虚构的训练信息。",
        risk_level=AgentRiskLevel.UNKNOWN,
        trace_id=request.request_id,
    )

    keys = response.model_dump(mode="json").keys()
    assert "user_id" not in keys
    assert "system_prompt" not in keys
    assert "exception" not in keys
    assert "traceback" not in keys
    assert isinstance(response.model_dump_json(), str)
