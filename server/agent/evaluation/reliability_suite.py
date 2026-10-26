"""Fixed, fictional Coach cases for local provider reliability evaluation.

The case set contains no real runner, conversation, health, or provider data.
It describes task contracts only; operator-run artifacts keep aggregate metrics
and deliberately omit raw prompts, outputs, and reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass

from server.agent.enums import AgentIntent


@dataclass(frozen=True)
class CoachReliabilityCase:
    case_id: str
    intent: AgentIntent
    fixture_name: str
    prompt: str
    expected_profile: str
    minimum_context_facts: int
    requires_limitation: bool = False
    must_not_apply_plan: bool = True


def coach_reliability_cases() -> tuple[CoachReliabilityCase, ...]:
    """Return the eight reviewed synthetic tasks used across model profiles."""

    return (
        CoachReliabilityCase(
            "daily_plan_fact",
            AgentIntent.PERSONAL_TRAINING_FACT_QUERY,
            "normal_training",
            "What is the fictional plan for tomorrow?",
            "coach_facts",
            1,
        ),
        CoachReliabilityCase(
            "recent_load_status",
            AgentIntent.PERSONAL_TRAINING_STATUS,
            "normal_training",
            "Summarize the fictional recent training status using available facts.",
            "coach_facts",
            3,
        ),
        CoachReliabilityCase(
            "quality_session_analysis",
            AgentIntent.PERSONAL_TRAINING_ANALYSIS,
            "high_fatigue_planned_interval",
            "Analyze the fictional recent quality-session execution and recovery limits.",
            "coach_analysis",
            6,
        ),
        CoachReliabilityCase(
            "two_week_race_analysis",
            AgentIntent.PERSONAL_TRAINING_ANALYSIS,
            "normal_training",
            "A fictional half marathon is two weeks away. Give a bounded analysis, not a plan write.",
            "coach_analysis",
            6,
        ),
        CoachReliabilityCase(
            "next_week_adjustment_analysis",
            AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
            "adjustment_recommended",
            "Analyze whether the fictional next-week workload needs an adjustment draft; do not apply it.",
            "plan_reasoning",
            6,
        ),
        CoachReliabilityCase(
            "missing_data_boundary",
            AgentIntent.PERSONAL_TRAINING_ANALYSIS,
            "missing_heart_rate",
            "Analyze the fictional training situation and clearly state the data gap.",
            "coach_analysis",
            6,
            requires_limitation=True,
        ),
        CoachReliabilityCase(
            "conflicted_or_unknown_facts",
            AgentIntent.PERSONAL_TRAINING_ANALYSIS,
            "unknown_runner_state",
            "Analyze the fictional current state only within available facts and uncertainties.",
            "coach_analysis",
            6,
            requires_limitation=True,
        ),
        CoachReliabilityCase(
            "no_unnecessary_plan_change",
            AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
            "normal_training",
            "Assess the fictional next week and explain if no formal plan change should be applied.",
            "plan_reasoning",
            6,
        ),
    )
