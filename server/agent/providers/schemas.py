from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from server.agent.enums import AgentIntent, AgentRiskLevel
from server.agent.schemas import (
    AgentNotice,
    AgentToolInvocation,
    MAX_CONTEXT_ITEMS,
    MAX_MODEL_TOOL_CALLS,
    MAX_NOTICES,
)


class ProviderContractModel(BaseModel):
    """Strict provider-only contract that is never exposed through OpenAPI."""

    model_config = ConfigDict(extra="forbid")


class ProviderTodayModelOutput(ProviderContractModel):
    """TODAY narrative selection without server-owned training facts."""

    answer: str = Field(min_length=1, max_length=12000)
    summary: str = Field(min_length=1, max_length=1000)
    key_evidence_ids: list[str] = Field(max_length=10)
    knowledge_reference_ids: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("key_evidence_ids", mode="before")
    @classmethod
    def validate_evidence_id_types(cls, value: Any) -> Any:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("key_evidence_ids must contain only strings")
        return value

    @field_validator("key_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[str]) -> list[str]:
        if any(
            not item
            or item.strip() != item
            or not item.startswith("evidence_")
            or not item.removeprefix("evidence_").isdigit()
            or item.removeprefix("evidence_").startswith("0")
            for item in value
        ):
            raise ValueError("key_evidence_ids contains an invalid request-local ID")
        if len(value) != len(set(value)):
            raise ValueError("key_evidence_ids must be unique")
        return value

    @field_validator("knowledge_reference_ids", mode="before")
    @classmethod
    def validate_knowledge_id_types(cls, value: Any) -> Any:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("knowledge_reference_ids must contain only strings")
        return value

    @field_validator("knowledge_reference_ids")
    @classmethod
    def validate_knowledge_ids(cls, value: list[str]) -> list[str]:
        if any(
            not item
            or item.strip() != item
            or not item.startswith("knowledge_")
            or not item.removeprefix("knowledge_").isdigit()
            or item.removeprefix("knowledge_").startswith("0")
            for item in value
        ):
            raise ValueError("knowledge_reference_ids contains an invalid request-local ID")
        if len(value) != len(set(value)):
            raise ValueError("knowledge_reference_ids must be unique")
        return value


class ProviderAgentModelOutput(ProviderContractModel):
    """Non-TODAY structured output; TODAY uses ProviderTodayModelOutput."""

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
    knowledge_reference_ids: list[str] = Field(default_factory=list, max_length=6)
    today_recommendation: None = None

    @field_validator("knowledge_reference_ids", mode="before")
    @classmethod
    def validate_knowledge_id_types(cls, value: Any) -> Any:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("knowledge_reference_ids must contain only strings")
        return value

    @model_validator(mode="after")
    def validate_tool_call_ids(self) -> "ProviderAgentModelOutput":
        ids = [item.tool_call_id for item in self.tool_calls]
        if len(ids) != len(set(ids)):
            raise ValueError("tool_call_id must be unique")
        if len(self.used_tool_call_ids) != len(set(self.used_tool_call_ids)):
            raise ValueError("used_tool_call_ids must be unique")
        if len(self.knowledge_reference_ids) != len(set(self.knowledge_reference_ids)):
            raise ValueError("knowledge_reference_ids must be unique")
        if any(
            not item
            or item.strip() != item
            or not item.startswith("knowledge_")
            or not item.removeprefix("knowledge_").isdigit()
            or item.removeprefix("knowledge_").startswith("0")
            for item in self.knowledge_reference_ids
        ):
            raise ValueError("knowledge_reference_ids contains an invalid request-local ID")
        return self


@dataclass(frozen=True)
class AgentProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    duration_ms: float | None = None
    status: str = "NOT_CALLED"
    safe_error_code: str | None = None
