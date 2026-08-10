from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from server.agent.enums import AgentTraceEventType, AgentTraceStatus
from server.agent.errors import AgentErrorCode
from server.agent.schemas import AgentContractModel


class AgentTraceEvent(AgentContractModel):
    event_type: AgentTraceEventType
    timestamp: datetime
    tool_name: str | None = Field(default=None, max_length=80)
    status: AgentTraceStatus
    safe_error_code: AgentErrorCode | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    provider_alias: str | None = Field(default=None, max_length=40)
    model_alias: str | None = Field(default=None, max_length=128)
    response_format_mode: Literal["json_schema", "json_object"] | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    provider_kind: str | None = Field(default=None, max_length=40)
    attempt: int | None = Field(default=None, ge=1, le=10)
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    failure_category: str | None = Field(default=None, max_length=80)
    retried: bool | None = None
    final_status: str | None = Field(default=None, max_length=40)


class AgentTrace(AgentContractModel):
    trace_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    events: list[AgentTraceEvent] = Field(default_factory=list, max_length=200)

    def add_event(
        self,
        event_type: AgentTraceEventType,
        status: AgentTraceStatus,
        *,
        tool_name: str | None = None,
        safe_error_code: AgentErrorCode | None = None,
        duration_ms: float | None = None,
        provider_alias: str | None = None,
        model_alias: str | None = None,
        response_format_mode: Literal["json_schema", "json_object"] | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        provider_kind: str | None = None,
        attempt: int | None = None,
        max_attempts: int | None = None,
        failure_category: str | None = None,
        retried: bool | None = None,
        final_status: str | None = None,
    ) -> None:
        self.events.append(
            AgentTraceEvent(
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                tool_name=tool_name,
                status=status,
                safe_error_code=safe_error_code,
                duration_ms=duration_ms,
                provider_alias=provider_alias,
                model_alias=model_alias,
                response_format_mode=response_format_mode,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                provider_kind=provider_kind,
                attempt=attempt,
                max_attempts=max_attempts,
                failure_category=failure_category,
                retried=retried,
                final_status=final_status,
            )
        )
