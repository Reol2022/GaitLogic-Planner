from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentToolDefinition


class AgentTool(ABC):
    """Explicit tool contract. Registry never accepts raw callables."""

    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]
    output_model: ClassVar[type[BaseModel]]
    read_only: ClassVar[bool] = True
    requires_confirmation: ClassVar[bool] = False
    allowed_intents: ClassVar[tuple[AgentIntent, ...]]

    @property
    def definition(self) -> AgentToolDefinition:
        return AgentToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
            read_only=self.read_only,
            requires_confirmation=self.requires_confirmation,
            allowed_intents=list(self.allowed_intents),
        )

    @abstractmethod
    def execute(self, arguments: BaseModel, context: AgentContext) -> BaseModel | dict:
        """Execute a bounded operation and return data matching ``output_model``."""

