"""Deterministic Coach fact and knowledge retrieval policy.

The policy is deliberately evaluated before the model runs.  It selects only
bounded read-only facts and keeps knowledge retrieval separate from personal
data access, so a routing miss can never use RAG as a substitute for runner
facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from server.agent.enums import AgentIntent


ToolPreload = tuple[str, dict[str, int | str]]
KnowledgeRetrievalMode = Literal["never", "required"]


@dataclass(frozen=True)
class RequiredFactsPolicy:
    """Bounded, request-local context requirements for one Coach intent."""

    intent: AgentIntent
    required_fact_set: tuple[str, ...]
    tool_preloads: tuple[ToolPreload, ...]
    knowledge_retrieval: KnowledgeRetrievalMode

    @property
    def requires_knowledge_retrieval(self) -> bool:
        return self.knowledge_retrieval == "required"


_POLICIES: dict[AgentIntent, RequiredFactsPolicy] = {
    AgentIntent.CASUAL_CONVERSATION: RequiredFactsPolicy(
        intent=AgentIntent.CASUAL_CONVERSATION,
        required_fact_set=(),
        tool_preloads=(),
        knowledge_retrieval="never",
    ),
    AgentIntent.COACH_CAPABILITY_QUERY: RequiredFactsPolicy(
        intent=AgentIntent.COACH_CAPABILITY_QUERY,
        required_fact_set=(),
        tool_preloads=(),
        knowledge_retrieval="never",
    ),
    AgentIntent.TODAY_RECOMMENDATION: RequiredFactsPolicy(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        required_fact_set=("runner_state", "today_workout", "recent_training", "data_quality", "today_evaluation"),
        tool_preloads=(
            ("get_runner_state", {}),
            ("get_today_workout", {}),
            ("get_recent_training", {"days": 7, "limit": 20}),
            ("get_training_data_quality", {"window_days": 14}),
            ("evaluate_today_workout", {}),
        ),
        knowledge_retrieval="required",
    ),
    AgentIntent.WEEKLY_REVIEW: RequiredFactsPolicy(
        intent=AgentIntent.WEEKLY_REVIEW,
        required_fact_set=("runner_state", "runner_state_history", "recent_training", "current_cycle", "data_quality"),
        tool_preloads=(
            ("get_runner_state", {}),
            ("get_runner_state_history", {"limit": 7}),
            ("get_recent_training", {"days": 7, "limit": 20}),
            ("get_current_training_cycle", {}),
            ("get_training_data_quality", {"window_days": 14}),
        ),
        knowledge_retrieval="never",
    ),
    AgentIntent.EXPLAIN_RUNNER_STATE: RequiredFactsPolicy(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        required_fact_set=("runner_state", "runner_state_history", "data_quality"),
        tool_preloads=(
            ("get_runner_state", {}),
            ("get_runner_state_history", {"limit": 7}),
            ("get_training_data_quality", {"window_days": 14}),
        ),
        knowledge_retrieval="required",
    ),
    AgentIntent.GENERAL_TRAINING_QUESTION: RequiredFactsPolicy(
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        required_fact_set=("general_training_rules",),
        tool_preloads=(("get_training_rules", {"scope": "GENERAL"}),),
        knowledge_retrieval="required",
    ),
    AgentIntent.PERSONAL_TRAINING_ANALYSIS: RequiredFactsPolicy(
        intent=AgentIntent.PERSONAL_TRAINING_ANALYSIS,
        required_fact_set=("runner_state", "runner_state_history", "recent_training", "current_cycle", "today_workout", "data_quality"),
        tool_preloads=(
            ("get_runner_state", {}),
            ("get_runner_state_history", {"limit": 7}),
            ("get_recent_training", {"days": 28, "limit": 20}),
            ("get_current_training_cycle", {}),
            ("get_today_workout", {}),
            ("get_training_data_quality", {"window_days": 28}),
        ),
        knowledge_retrieval="never",
    ),
    AgentIntent.PLAN_ADJUSTMENT_ANALYSIS: RequiredFactsPolicy(
        intent=AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
        required_fact_set=("runner_state", "runner_state_history", "recent_training", "current_cycle", "today_workout", "data_quality"),
        tool_preloads=(
            ("get_runner_state", {}),
            ("get_runner_state_history", {"limit": 7}),
            ("get_recent_training", {"days": 28, "limit": 20}),
            ("get_current_training_cycle", {}),
            ("get_today_workout", {}),
            ("get_training_data_quality", {"window_days": 28}),
        ),
        knowledge_retrieval="never",
    ),
    AgentIntent.PERSONAL_TRAINING_STATUS: RequiredFactsPolicy(
        intent=AgentIntent.PERSONAL_TRAINING_STATUS,
        required_fact_set=("runner_state", "recent_training", "data_quality"),
        tool_preloads=(
            ("get_runner_state", {}),
            ("get_recent_training", {"days": 14, "limit": 14}),
            ("get_training_data_quality", {"window_days": 14}),
        ),
        knowledge_retrieval="never",
    ),
    AgentIntent.UNKNOWN: RequiredFactsPolicy(
        intent=AgentIntent.UNKNOWN,
        required_fact_set=(),
        tool_preloads=(),
        knowledge_retrieval="never",
    ),
}


def resolve_required_facts_policy(
    *, intent: AgentIntent, message: str, current_time: datetime
) -> RequiredFactsPolicy:
    """Return the bounded policy for this request without executing any tool."""
    if intent != AgentIntent.PERSONAL_TRAINING_FACT_QUERY:
        return _POLICIES[intent]

    normalized = message.lower()
    target_date = current_time.date() + timedelta(days=1) if any(
        marker in normalized for marker in ("\u660e\u5929", "\u660e\u65e5", "tomorrow")
    ) else current_time.date()
    return RequiredFactsPolicy(
        intent=intent,
        required_fact_set=("today_workout",),
        tool_preloads=(("get_today_workout", {"target_date": target_date.isoformat()}),),
        knowledge_retrieval="never",
    )
