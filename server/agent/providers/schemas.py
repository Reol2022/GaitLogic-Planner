from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    duration_ms: float | None = None
    status: str = "NOT_CALLED"
    safe_error_code: str | None = None
