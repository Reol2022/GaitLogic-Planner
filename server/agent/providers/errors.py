from __future__ import annotations

from server.agent.errors import AgentErrorCode


class AgentProviderError(Exception):
    """Provider failure carrying only a public-safe error code."""

    def __init__(self, code: AgentErrorCode) -> None:
        super().__init__(code.value)
        self.code = code
