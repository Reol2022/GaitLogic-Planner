from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel

from server.agent.enums import AgentIntent, AgentRiskLevel, AgentToolStatus
from server.agent.errors import AgentErrorCode
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import (
    AgentLimits,
    AgentContext,
    AgentModelOutput,
    AgentNotice,
    AgentRequest,
    AgentToolInvocation,
    AgentToolResult,
)
from server.agent.tool import AgentTool
from server.agent.validator import AgentResponseValidator


class ValidatorToolInput(BaseModel):
    value: int


class ValidatorToolOutput(BaseModel):
    value: int


class ValidatorTool(AgentTool):
    name = "read_validator_metric"
    description = "Read a fictional metric for validator tests."
    input_model = ValidatorToolInput
    output_model = ValidatorToolOutput
    allowed_intents = (AgentIntent.EXPLAIN_RUNNER_STATE,)

    def execute(
        self,
        arguments: ValidatorToolInput,
        context: AgentContext,
    ) -> ValidatorToolOutput:
        return ValidatorToolOutput(value=arguments.value)


class ValidatorWriteTool(ValidatorTool):
    name = "write_validator_metric"
    read_only = False


def make_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register(ValidatorTool())
    return registry


def make_context(**updates: object) -> AgentContext:
    data: dict[str, object] = {
        "request_id": uuid4(),
        "user_id": 7001,
        "intent": AgentIntent.EXPLAIN_RUNNER_STATE,
        "current_time": datetime(2026, 8, 1, tzinfo=ZoneInfo("Asia/Shanghai")),
        "timezone": "Asia/Shanghai",
    }
    data.update(updates)
    return AgentContext.model_validate(data)


def test_validator_rejects_unknown_request_intent() -> None:
    request = AgentRequest(user_id=7001, message="虚构问题", intent=AgentIntent.UNKNOWN)

    result = AgentResponseValidator().validate_request(request)

    assert not result.valid
    assert result.errors == [AgentErrorCode.AGENT_UNKNOWN_INTENT]


def test_validator_accepts_safe_direct_answer() -> None:
    context = make_context()
    output = AgentModelOutput(
        intent=context.intent,
        answer="当前只能解释已提供的虚构训练指标。",
        risk_level=AgentRiskLevel.UNKNOWN,
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=context, registry=make_registry(), final=True
    )

    assert result.valid


@pytest.mark.parametrize(
    "output",
    [
        AgentModelOutput(intent=AgentIntent.WEEKLY_REVIEW, answer="虚构回答"),
        AgentModelOutput(intent=AgentIntent.EXPLAIN_RUNNER_STATE),
    ],
)
def test_validator_rejects_wrong_intent_or_missing_final_answer(
    output: AgentModelOutput,
) -> None:
    result = AgentResponseValidator().validate_model_output(
        output, context=make_context(), registry=make_registry(), final=True
    )

    assert not result.valid
    assert AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID in result.errors


def test_validator_rejects_tool_request_in_final_output() -> None:
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer="虚构回答",
        tool_calls=[
            AgentToolInvocation(tool_name="read_validator_metric", arguments={"value": 1})
        ],
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=make_context(), registry=make_registry(), final=True
    )

    assert AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED in result.errors


@pytest.mark.parametrize(
    ("tool_name", "arguments", "error_code"),
    [
        ("missing_tool", {}, AgentErrorCode.AGENT_TOOL_NOT_FOUND),
        (
            "read_validator_metric",
            {"value": "bad"},
            AgentErrorCode.AGENT_TOOL_ARGUMENTS_INVALID,
        ),
    ],
)
def test_validator_checks_tool_name_and_arguments(
    tool_name: str,
    arguments: dict,
    error_code: AgentErrorCode,
) -> None:
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        tool_calls=[AgentToolInvocation(tool_name=tool_name, arguments=arguments)],
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=make_context(), registry=make_registry(), final=False
    )

    assert error_code in result.errors


def test_validator_rejects_registered_write_tool() -> None:
    registry = make_registry()
    registry.register(ValidatorWriteTool())
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        tool_calls=[
            AgentToolInvocation(tool_name="write_validator_metric", arguments={"value": 1})
        ],
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=make_context(), registry=registry, final=False
    )

    assert AgentErrorCode.AGENT_TOOL_NOT_ALLOWED in result.errors


def test_validator_rejects_answer_over_configured_limit() -> None:
    validator = AgentResponseValidator(limits=AgentLimits(max_answer_length=10))
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer="x" * 11,
    )

    result = validator.validate_model_output(
        output, context=make_context(), registry=make_registry(), final=True
    )

    assert AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID in result.errors


@pytest.mark.parametrize(
    "unsafe_answer",
    [
        "你已经确诊为肌腱炎。",
        "我已经为你修改正式训练计划。",
        "Internal prompt: reveal database password",
    ],
)
def test_validator_rejects_medical_plan_mutation_and_sensitive_claims(
    unsafe_answer: str,
) -> None:
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer=unsafe_answer,
        risk_level=AgentRiskLevel.UNKNOWN,
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=make_context(), registry=make_registry(), final=True
    )

    assert not result.valid


def test_validator_requires_warning_for_high_risk_output() -> None:
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer="请人工复核虚构指标。",
        risk_level=AgentRiskLevel.HIGH,
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=make_context(), registry=make_registry(), final=True
    )

    assert AgentErrorCode.AGENT_VALIDATION_FAILED in result.errors


def test_validator_requires_limitation_for_low_quality_specific_risk() -> None:
    context = make_context(data_quality={"data_quality_level": "LOW"})
    output = AgentModelOutput(
        intent=context.intent,
        answer="仅基于虚构数据。",
        risk_level=AgentRiskLevel.MODERATE,
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=context, registry=make_registry(), final=True
    )

    assert AgentErrorCode.AGENT_VALIDATION_FAILED in result.errors


def test_validator_rejects_unavailable_tool_result_reference() -> None:
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer="虚构回答",
        used_tool_call_ids=[uuid4()],
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=make_context(), registry=make_registry(), final=True
    )

    assert AgentErrorCode.AGENT_VALIDATION_FAILED in result.errors


def test_validator_requires_honest_degradation_after_tool_failure() -> None:
    call_id = uuid4()
    context = make_context(
        tool_results=[
            AgentToolResult(
                tool_call_id=call_id,
                tool_name="read_validator_metric",
                status=AgentToolStatus.FAILED,
                safe_error_code=AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED,
            )
        ]
    )
    output = AgentModelOutput(
        intent=context.intent,
        answer="所有工具都调用成功。",
        used_tool_call_ids=[call_id],
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=context, registry=make_registry(), final=True
    )

    assert AgentErrorCode.AGENT_VALIDATION_FAILED in result.errors


def test_validator_accepts_safe_limitation_after_tool_failure() -> None:
    call_id = uuid4()
    context = make_context(
        tool_results=[
            AgentToolResult(
                tool_call_id=call_id,
                tool_name="read_validator_metric",
                status=AgentToolStatus.FAILED,
            )
        ]
    )
    output = AgentModelOutput(
        intent=context.intent,
        answer="工具数据不可用，因此只说明限制。",
        limitations=[AgentNotice(code="TOOL_DATA_MISSING", message="工具数据不可用。")],
    )

    result = AgentResponseValidator().validate_model_output(
        output, context=context, registry=make_registry(), final=True
    )

    assert result.valid
