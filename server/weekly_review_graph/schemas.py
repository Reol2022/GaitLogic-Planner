from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from planner_core.weekly_review.schemas import WeeklyFacts, WeeklyFactsRequest
from server.agent.schemas import AgentKnowledgeReference
from server.agent.tools.knowledge_tools import KnowledgeToolResultItem


class GraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WeeklyReviewGraphStatus(str, Enum):
    PENDING = "PENDING"
    FACTS_READY = "FACTS_READY"
    RULES_READY = "RULES_READY"
    KNOWLEDGE_READY = "KNOWLEDGE_READY"
    DRAFT_READY = "DRAFT_READY"
    VALIDATED = "VALIDATED"
    FALLBACK = "FALLBACK"
    COMPLETED = "COMPLETED"


class WeeklyReviewDraft(GraphModel):
    overview: str = Field(min_length=1, max_length=2000)
    completion_summary: str = Field(min_length=1, max_length=2000)
    key_session_summary: str = Field(min_length=1, max_length=2000)
    deviation_summary: str = Field(min_length=1, max_length=2000)
    fatigue_and_risk: str = Field(min_length=1, max_length=2000)
    next_week_focus: list[str] = Field(default_factory=list, max_length=8)
    knowledge_reference_ids: list[str] = Field(default_factory=list, max_length=6)


class WeeklyReviewResult(GraphModel):
    weekly_facts: WeeklyFacts
    rule_results: list[str]
    overview: str
    completion_summary: str
    key_session_summary: str
    deviation_summary: str
    fatigue_and_risk: str
    next_week_focus: list[str]
    warnings: list[str]
    limitations: list[str]
    knowledge_references: list[AgentKnowledgeReference]
    fallback_used: bool


class WeeklyReviewState(GraphModel):
    user_id: int = Field(gt=0)
    request: WeeklyFactsRequest
    weekly_facts: WeeklyFacts | None = None
    rule_results: list[str] = Field(default_factory=list)
    knowledge_results: list[KnowledgeToolResultItem] = Field(default_factory=list)
    knowledge_reference_ids: list[str] = Field(default_factory=list)
    review_draft: WeeklyReviewDraft | None = None
    validated_review: WeeklyReviewDraft | None = None
    final_review: WeeklyReviewResult | None = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trace_context: dict[str, Any] = Field(default_factory=dict)
    status: WeeklyReviewGraphStatus = WeeklyReviewGraphStatus.PENDING
    validation_errors: list[str] = Field(default_factory=list)
