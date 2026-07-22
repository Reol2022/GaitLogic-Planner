from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from server.agent.enums import AgentIntent, AgentRiskLevel, AgentRunStatus, AgentToolStatus
from server.agent.errors import AgentErrorCode

MAX_MESSAGE_LENGTH = 4000
MAX_CONVERSATION_ITEMS = 50
MAX_CONVERSATION_ITEM_LENGTH = 2000
MAX_CONVERSATION_CHARS = 12000
MAX_CONTEXT_ITEMS = 50
MAX_CONTEXT_JSON_CHARS = 50000
MAX_MODEL_TOOL_CALLS = 50
MAX_NOTICES = 20


class AgentContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentConversationMessage(AgentContractModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CONVERSATION_ITEM_LENGTH)


class AgentRequest(AgentContractModel):
    """Internal request. Authentication code must inject ``user_id``."""

    user_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    intent: AgentIntent
    conversation_context: list[AgentConversationMessage] = Field(
        default_factory=list,
        max_length=MAX_CONVERSATION_ITEMS,
    )
    request_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def validate_conversation_size(self) -> "AgentRequest":
        total = sum(len(item.content) for item in self.conversation_context)
        if total > MAX_CONVERSATION_CHARS:
            raise ValueError("conversation context is too large")
        return self

    @classmethod
    def for_authenticated_user(
        cls,
        *,
        user_id: int,
        message: str,
        intent: AgentIntent,
        conversation_context: list[AgentConversationMessage] | None = None,
    ) -> "AgentRequest":
        return cls(
            user_id=user_id,
            message=message,
            intent=intent,
            conversation_context=conversation_context or [],
            request_id=uuid4(),
        )


class AgentNotice(AgentContractModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    message: str = Field(min_length=1, max_length=300)


class AgentToolDefinition(AgentContractModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1, max_length=500)
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    read_only: bool = True
    requires_confirmation: bool = False
    allowed_intents: list[AgentIntent] = Field(min_length=1, max_length=len(AgentIntent))

    @model_validator(mode="after")
    def validate_unique_intents(self) -> "AgentToolDefinition":
        if len(self.allowed_intents) != len(set(self.allowed_intents)):
            raise ValueError("allowed_intents must be unique")
        return self


class AgentToolInvocation(AgentContractModel):
    tool_call_id: UUID = Field(default_factory=uuid4)
    tool_name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class AgentToolResult(AgentContractModel):
    tool_call_id: UUID
    tool_name: str
    status: AgentToolStatus
    data: JsonValue | None = None
    safe_error_code: AgentErrorCode | None = None
    warnings: list[AgentNotice] = Field(default_factory=list, max_length=MAX_NOTICES)


class AgentContextSeed(AgentContractModel):
    runner_state: dict[str, JsonValue] | None = None
    runner_state_history: dict[str, JsonValue] | None = None
    recent_training: dict[str, JsonValue] | None = None
    today_workout: dict[str, JsonValue] | None = None
    current_cycle: dict[str, JsonValue] | None = None
    today_evaluation: dict[str, JsonValue] | None = None
    applicable_rules: list[dict[str, JsonValue]] = Field(
        default_factory=list,
        max_length=MAX_CONTEXT_ITEMS,
    )
    data_quality: dict[str, JsonValue] | None = None
    missing_reasons: dict[str, str] = Field(default_factory=dict, max_length=MAX_CONTEXT_ITEMS)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=MAX_NOTICES)


class AgentContext(AgentContractModel):
    request_id: UUID
    user_id: int = Field(gt=0)
    intent: AgentIntent
    current_time: datetime
    timezone: str = Field(min_length=1, max_length=64)
    conversation_context: list[AgentConversationMessage] = Field(
        default_factory=list,
        max_length=MAX_CONVERSATION_ITEMS,
    )
    runner_state: dict[str, JsonValue] | None = None
    runner_state_history: dict[str, JsonValue] | None = None
    recent_training: dict[str, JsonValue] | None = None
    today_workout: dict[str, JsonValue] | None = None
    current_cycle: dict[str, JsonValue] | None = None
    today_evaluation: dict[str, JsonValue] | None = None
    applicable_rules: list[dict[str, JsonValue]] = Field(
        default_factory=list,
        max_length=MAX_CONTEXT_ITEMS,
    )
    data_quality: dict[str, JsonValue] | None = None
    tool_results: list[AgentToolResult] = Field(default_factory=list, max_length=MAX_CONTEXT_ITEMS)
    missing_reasons: dict[str, str] = Field(default_factory=dict, max_length=MAX_CONTEXT_ITEMS)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=MAX_NOTICES)

    @model_validator(mode="after")
    def validate_context_size(self) -> "AgentContext":
        raw = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        if len(raw) > MAX_CONTEXT_JSON_CHARS:
            raise ValueError("agent context is too large")
        if self.current_time.tzinfo is None or self.current_time.utcoffset() is None:
            raise ValueError("current_time must be timezone-aware")
        return self


class AgentTodayRecommendation(AgentContractModel):
    decision: Literal[
        "PROCEED",
        "PROCEED_WITH_CAUTION",
        "CONSIDER_ADJUSTMENT",
        "REST_OR_RECOVERY",
        "UNKNOWN",
    ]
    planned_workout_status: Literal[
        "PLANNED",
        "REST_DAY",
        "NO_PLAN",
        "CYCLE_NOT_ACTIVE",
        "UNKNOWN",
    ]
    headline: str = Field(min_length=1, max_length=300)
    key_evidence: list[str] = Field(default_factory=list, max_length=10)
    data_quality: str = Field(min_length=1, max_length=40)


class AgentModelOutput(AgentContractModel):
    answer: str | None = Field(default=None, max_length=12000)
    summary: str | None = Field(default=None, max_length=1000)
    intent: AgentIntent
    tool_calls: list[AgentToolInvocation] = Field(
        default_factory=list,
        max_length=MAX_MODEL_TOOL_CALLS,
    )
    risk_level: AgentRiskLevel = AgentRiskLevel.UNKNOWN
    warnings: list[AgentNotice] = Field(default_factory=list, max_length=MAX_NOTICES)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=MAX_NOTICES)
    used_tool_call_ids: list[UUID] = Field(default_factory=list, max_length=MAX_CONTEXT_ITEMS)
    today_recommendation: AgentTodayRecommendation | None = None

    @model_validator(mode="after")
    def validate_tool_call_ids(self) -> "AgentModelOutput":
        ids = [item.tool_call_id for item in self.tool_calls]
        if len(ids) != len(set(ids)):
            raise ValueError("tool_call_id must be unique")
        if len(self.used_tool_call_ids) != len(set(self.used_tool_call_ids)):
            raise ValueError("used_tool_call_ids must be unique")
        return self


class AgentToolCallSummary(AgentContractModel):
    tool_call_id: UUID
    tool_name: str
    status: AgentToolStatus
    safe_error_code: AgentErrorCode | None = None


class AgentResponse(AgentContractModel):
    request_id: UUID
    status: AgentRunStatus
    intent: AgentIntent
    answer: str | None = None
    summary: str | None = None
    risk_level: AgentRiskLevel
    tool_calls: list[AgentToolCallSummary] = Field(default_factory=list, max_length=MAX_CONTEXT_ITEMS)
    warnings: list[AgentNotice] = Field(default_factory=list, max_length=MAX_NOTICES)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=MAX_NOTICES)
    trace_id: UUID
    today_recommendation: AgentTodayRecommendation | None = None


class AgentValidationResult(AgentContractModel):
    valid: bool
    errors: list[AgentErrorCode] = Field(default_factory=list)


class AgentLimits(AgentContractModel):
    max_model_calls: int = Field(default=2, ge=1, le=2)
    max_tool_calls: int = Field(default=6, ge=0, le=20)
    max_same_tool_calls: int = Field(default=2, ge=1, le=6)
    max_message_length: int = Field(default=MAX_MESSAGE_LENGTH, ge=1, le=12000)
    max_context_items: int = Field(default=MAX_CONTEXT_ITEMS, ge=1, le=200)
    max_context_chars: int = Field(
        default=MAX_CONTEXT_JSON_CHARS,
        ge=5000,
        le=MAX_CONTEXT_JSON_CHARS,
    )
    max_recent_training_items: int = Field(default=20, ge=1, le=50)
    max_history_items: int = Field(default=7, ge=1, le=14)
    max_evidence_items: int = Field(default=5, ge=1, le=20)
    max_rule_items: int = Field(default=20, ge=1, le=50)
    max_answer_length: int = Field(default=6000, ge=1, le=12000)
