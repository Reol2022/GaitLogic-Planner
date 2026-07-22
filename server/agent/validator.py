from __future__ import annotations

import re

from pydantic import ValidationError

from server.agent.enums import AgentIntent, AgentRiskLevel, AgentToolStatus
from server.agent.errors import AgentErrorCode
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import (
    AgentContext,
    AgentLimits,
    AgentModelOutput,
    AgentRequest,
    AgentValidationResult,
)

_MEDICAL_DIAGNOSIS_PATTERNS = (
    r"(?:已经|就是|患有|得了).{0,12}(?:骨折|肌腱炎|心肌炎|疾病)",
    r"确诊为",
    r"伤病概率为",
    r"you (?:have|are diagnosed with)",
)
_PLAN_MUTATION_PATTERNS = (
    r"(?:已经(?:为你)?|已为你)(?:修改|调整|生成).{0,12}(?:正式)?训练计划",
    r"i (?:updated|changed|applied) your (?:official )?training plan",
)
_SENSITIVE_OUTPUT_PATTERNS = (
    r"system prompt",
    r"internal prompt",
    r"系统提示词",
    r"内部提示词",
    r"api[_ ]?key",
    r"authorization:\s*bearer",
    r"garmin[_ ]?token",
    r"database password",
    r"数据库密码",
    r"begin (?:rsa )?private key",
    r"traceback \(most recent call last\)",
)
_FALSE_TOOL_SUCCESS_PATTERNS = (
    r"所有工具(?:均|都)调用成功",
    r"工具调用成功",
    r"all tools succeeded",
)
_LOW_DATA_QUALITY_VALUES = {"LOW", "INSUFFICIENT", "UNKNOWN"}


class AgentResponseValidator:
    """Deterministic safety checks applied before any response is returned."""

    def __init__(self, limits: AgentLimits | None = None) -> None:
        self.limits = limits or AgentLimits()

    @staticmethod
    def _result(errors: list[AgentErrorCode]) -> AgentValidationResult:
        unique = list(dict.fromkeys(errors))
        return AgentValidationResult(valid=not unique, errors=unique)

    def validate_request(self, request: AgentRequest) -> AgentValidationResult:
        errors: list[AgentErrorCode] = []
        if not request.message or len(request.message) > self.limits.max_message_length:
            errors.append(AgentErrorCode.AGENT_INVALID_REQUEST)
        if request.intent == AgentIntent.UNKNOWN:
            errors.append(AgentErrorCode.AGENT_UNKNOWN_INTENT)
        return self._result(errors)

    def validate_model_output(
        self,
        output: AgentModelOutput,
        *,
        context: AgentContext,
        registry: AgentToolRegistry,
        final: bool,
    ) -> AgentValidationResult:
        errors: list[AgentErrorCode] = []
        if output.intent != context.intent:
            errors.append(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID)
        if final and not output.answer:
            errors.append(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID)
        if output.answer is not None and len(output.answer) > self.limits.max_answer_length:
            errors.append(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID)
        if len(output.tool_calls) > self.limits.max_tool_calls:
            errors.append(AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED)
        if final and output.tool_calls:
            errors.append(AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED)

        for invocation in output.tool_calls:
            tool = registry.get(invocation.tool_name)
            if tool is None:
                errors.append(AgentErrorCode.AGENT_TOOL_NOT_FOUND)
                continue
            definition = tool.definition
            if not definition.read_only or context.intent not in definition.allowed_intents:
                errors.append(AgentErrorCode.AGENT_TOOL_NOT_ALLOWED)
                continue
            try:
                tool.input_model.model_validate(invocation.arguments)
            except ValidationError:
                errors.append(AgentErrorCode.AGENT_TOOL_ARGUMENTS_INVALID)

        text = "\n".join(
            item
            for item in [
                output.answer or "",
                output.summary or "",
                *(notice.message for notice in output.warnings),
                *(notice.message for notice in output.limitations),
            ]
            if item
        ).lower()
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in _MEDICAL_DIAGNOSIS_PATTERNS):
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in _PLAN_MUTATION_PATTERNS):
            errors.append(AgentErrorCode.AGENT_TOOL_NOT_ALLOWED)
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in _SENSITIVE_OUTPUT_PATTERNS):
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        if output.risk_level == AgentRiskLevel.HIGH and not output.warnings:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        data_quality = context.data_quality or {}
        quality_value = str(
            data_quality.get("data_quality_level") or data_quality.get("level") or ""
        ).upper()
        data_is_limited = bool(context.missing_reasons) or quality_value in _LOW_DATA_QUALITY_VALUES
        if data_is_limited and output.risk_level != AgentRiskLevel.UNKNOWN and not output.limitations:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        available_results = {item.tool_call_id for item in context.tool_results}
        if any(item not in available_results for item in output.used_tool_call_ids):
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        failed_results = [
            item for item in context.tool_results if item.status != AgentToolStatus.SUCCEEDED
        ]
        if failed_results:
            if not output.warnings and not output.limitations:
                errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in _FALSE_TOOL_SUCCESS_PATTERNS):
                errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        return self._result(errors)
