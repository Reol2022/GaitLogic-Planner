from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from server.agent.enums import AgentIntent, AgentRiskLevel, AgentToolStatus
from server.agent.errors import AgentErrorCode
from server.agent.schemas import (
    AgentContractModel,
    AgentConversationMessage,
    AgentNotice,
    AgentKnowledgeReference,
    AgentTodayRecommendation,
    MAX_CONVERSATION_ITEMS,
    MAX_CONVERSATION_CHARS,
    MAX_MESSAGE_LENGTH,
)


class CoachQueryRequest(AgentContractModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    intent: AgentIntent | None = None
    conversation_context: list[AgentConversationMessage] = Field(
        default_factory=list,
        max_length=MAX_CONVERSATION_ITEMS,
    )

    @model_validator(mode="after")
    def validate_conversation_size(self) -> "CoachQueryRequest":
        if sum(len(item.content) for item in self.conversation_context) > MAX_CONVERSATION_CHARS:
            raise PydanticCustomError(
                "conversation_context_too_large",
                "conversation context is too large",
            )
        return self


class CoachToolCallRead(AgentContractModel):
    tool_name: str
    status: AgentToolStatus
    safe_error_code: AgentErrorCode | None = None


class CoachKnowledgeReferenceRead(AgentKnowledgeReference):
    pass


class CoachQueryResponse(AgentContractModel):
    request_id: UUID
    trace_id: UUID
    status: Literal["SUCCEEDED", "DEGRADED", "VALIDATION_FAILED", "REJECTED", "UNAVAILABLE"]
    intent: AgentIntent
    answer: str | None = None
    summary: str | None = None
    risk_level: AgentRiskLevel
    today_recommendation: AgentTodayRecommendation | None = None
    tool_calls: list[CoachToolCallRead] = Field(default_factory=list, max_length=50)
    warnings: list[AgentNotice] = Field(default_factory=list, max_length=20)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)
    knowledge_references: list[CoachKnowledgeReferenceRead] = Field(
        default_factory=list,
        max_length=6,
    )
    provider_status: Literal[
        "SUCCEEDED",
        "DISABLED",
        "UNCONFIGURED",
        "FAILED",
        "NOT_CALLED",
    ]
    generated_at: datetime
