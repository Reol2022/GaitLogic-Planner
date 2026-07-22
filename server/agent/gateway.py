from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from server.agent.schemas import AgentContext, AgentModelOutput, AgentToolDefinition
from server.agent.trace import AgentTrace


class AgentLLMGateway(ABC):
    """Provider-neutral structured generation boundary."""

    @abstractmethod
    def generate(
        self,
        *,
        system_instructions: str,
        user_message: str,
        context: AgentContext,
        tools: list[AgentToolDefinition],
        trace: AgentTrace,
    ) -> AgentModelOutput:
        """Return validated structured output without exposing reasoning."""


class MockAgentLLMGateway(AgentLLMGateway):
    """Deterministic in-memory gateway for tests and local examples."""

    def __init__(
        self,
        outputs: AgentModelOutput | Mapping[str, Any] | Sequence[AgentModelOutput | Mapping[str, Any]],
        *,
        error: Exception | None = None,
    ) -> None:
        if isinstance(outputs, (AgentModelOutput, Mapping)):
            self._outputs = [outputs]
        else:
            self._outputs = list(outputs)
        self._error = error
        self.call_count = 0
        self.exposed_tool_names: list[list[str]] = []

    def generate(
        self,
        *,
        system_instructions: str,
        user_message: str,
        context: AgentContext,
        tools: list[AgentToolDefinition],
        trace: AgentTrace,
    ) -> AgentModelOutput:
        self.call_count += 1
        self.exposed_tool_names.append([item.name for item in tools])
        if self._error is not None:
            raise self._error
        index = self.call_count - 1
        if index >= len(self._outputs):
            raise RuntimeError("mock gateway output exhausted")
        return AgentModelOutput.model_validate(self._outputs[index])
