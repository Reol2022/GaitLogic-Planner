from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from server.agent.schemas import AgentContractModel
from server.schemas.coach_agent import (
    CoachKnowledgeReferenceRead,
    CoachQueryResponse,
    CoachToolCallRead,
)

ConversationStatus = Literal["active", "archived"]
MessageRole = Literal["user", "assistant"]
MessageStatus = Literal["pending", "completed", "failed"]


class CoachConversationCreate(AgentContractModel):
    title: str | None = Field(default=None, max_length=160)


class CoachConversationUpdate(AgentContractModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    status: ConversationStatus | None = None


class CoachConversationRead(AgentContractModel):
    id: str
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    message_count: int = Field(ge=0)


class CoachMessageRead(AgentContractModel):
    id: str
    role: MessageRole
    content: str | None = None
    status: MessageStatus
    sequence_no: int = Field(ge=1)
    response_kind: str | None = None
    evidence_refs: list[CoachKnowledgeReferenceRead] = Field(default_factory=list)
    proposal_ref: str | None = None
    trace_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    warnings: list[dict[str, str]] = Field(default_factory=list)
    limitations: list[dict[str, str]] = Field(default_factory=list)
    tool_calls: list[CoachToolCallRead] = Field(default_factory=list)
    today_recommendation: dict | None = None


class CoachConversationPage(AgentContractModel):
    items: list[CoachConversationRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total: int = Field(ge=0)


class CoachMessagePage(AgentContractModel):
    items: list[CoachMessageRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class CoachContextRef(AgentContractModel):
    kind: Literal["workout", "training_cycle", "weekly_review", "proposal"]
    id: str = Field(min_length=1, max_length=64)


class CoachConversationMessageCreate(AgentContractModel):
    client_turn_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message: str = Field(min_length=1, max_length=4000)
    context_ref: CoachContextRef | None = None


class CoachConversationMessageResult(AgentContractModel):
    conversation_id: str
    message_id: str
    status: MessageStatus
    content: str | None = None
    response: CoachQueryResponse | None = None
