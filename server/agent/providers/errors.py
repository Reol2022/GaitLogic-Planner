from __future__ import annotations

from server.agent.errors import AgentErrorCode
from server.provider_reliability import ProviderFailureCategory


class AgentProviderError(Exception):
    """Provider failure carrying only a public-safe error code."""

    def __init__(
        self,
        code: AgentErrorCode,
        *,
        category: ProviderFailureCategory = ProviderFailureCategory.PROVIDER_UNKNOWN_ERROR,
        finish_reason: str | None = None,
        reasoning_length: int = 0,
        content_length: int = 0,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.category = category
        self.finish_reason = finish_reason
        self.reasoning_length = reasoning_length
        self.content_length = content_length
