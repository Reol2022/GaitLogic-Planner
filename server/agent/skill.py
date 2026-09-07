from __future__ import annotations

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field

from server.agent.tool import AgentTool


class SkillStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class SkillResult(BaseModel):
    skill_name: str
    status: SkillStatus
    summary: str | None = None
    facts: dict = Field(default_factory=dict)
    evidence_refs: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
    proposal: dict | None = None
    requires_approval: bool = False


class AgentSkill(AgentTool):
    """A composite capability exposed through the existing tool protocol."""

    required_capabilities: ClassVar[tuple[str, ...]] = ()
    optional_capabilities: ClassVar[tuple[str, ...]] = ()
    cacheable: ClassVar[bool] = True
    visible_to_model: ClassVar[bool] = True
