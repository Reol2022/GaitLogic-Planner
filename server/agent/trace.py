from __future__ import annotations

from datetime import datetime, timezone
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
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


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
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
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
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )
