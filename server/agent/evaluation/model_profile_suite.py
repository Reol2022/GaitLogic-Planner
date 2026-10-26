"""Synthetic, non-production cases for comparing Coach execution profiles.

The suite deliberately stores task labels and expected routing only.  It never
contains a real chat, training record, provider response, token count, or chain
of-thought.  A separate operator-runner may attach provider outcomes locally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProfileName = Literal["chat_fast", "coach_facts", "coach_analysis", "plan_reasoning"]


@dataclass(frozen=True)
class ModelProfileEvaluationCase:
    case_id: str
    task_family: str
    expected_profile: ProfileName
    expected_fact_policy: str
    requires_rag: bool
    expected_tool_count: int


_FAMILIES: tuple[tuple[str, ProfileName, str, bool, int], ...] = (
    ("greeting", "chat_fast", "none", False, 0),
    ("capability_boundary", "chat_fast", "none", False, 0),
    ("single_plan_fact", "coach_facts", "target_date_plan", False, 1),
    ("recent_status", "coach_facts", "bounded_14_day_status", False, 3),
    ("personal_analysis", "coach_analysis", "bounded_28_day_analysis", False, 6),
    ("plan_adjustment_analysis", "plan_reasoning", "bounded_28_day_plan_analysis", False, 6),
)


def synthetic_model_profile_cases() -> tuple[ModelProfileEvaluationCase, ...]:
    """Return 30 stable synthetic tasks: five variations for each task family."""

    return tuple(
        ModelProfileEvaluationCase(
            case_id=f"profile_{family}_{variation}",
            task_family=family,
            expected_profile=profile,
            expected_fact_policy=fact_policy,
            requires_rag=requires_rag,
            expected_tool_count=tool_count,
        )
        for family, profile, fact_policy, requires_rag, tool_count in _FAMILIES
        for variation in range(1, 6)
    )
