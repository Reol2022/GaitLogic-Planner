from __future__ import annotations

from datetime import date

import pytest

from planner_core.adaptive_plan.schemas import (
    PlanValue,
    ProposalCandidateChange,
    TargetPlanFact,
)
from planner_core.enums import PlanAdjustmentAction
from planner_core.weekly_review.aggregation import build_weekly_facts
from planner_core.weekly_review.schemas import (
    PlannedSessionFact,
    RunnerStateSampleFact,
    WeeklyPeriod,
    WorkoutSessionFact,
)
from server.common.exceptions import BadRequestError
from server.services.adaptive_plan_proposal_service import AdaptivePlanProposalService


START = date(2026, 7, 6)
END = date(2026, 7, 12)


def facts(*, fatigue: str = "NORMAL", with_data: bool = True):
    plans = [PlannedSessionFact(plan_id=1, session_date=START, main_type="easy", distance_km=8)] if with_data else []
    logs = [WorkoutSessionFact(log_id=1, planned_workout_id=1, activity_date=START, main_type="easy", distance_km=8, duration_minutes=45, status="completed_normal")] if with_data else []
    samples = [
        RunnerStateSampleFact(sample_date=START, fatigue_state=fatigue),
        RunnerStateSampleFact(sample_date=END, fatigue_state=fatigue),
    ] if with_data else []
    return build_weekly_facts(
        period=WeeklyPeriod(week_start=START, week_end=END, timezone="Asia/Shanghai"),
        plans=plans,
        logs=logs,
        runner_state_samples=samples,
        as_of_date=END,
    )


def target(plan_id: int = 10, *, kind: str = "easy", distance: float = 10):
    return TargetPlanFact(
        plan_id=plan_id,
        user_id=7,
        workout_date=date(2026, 7, 13),
        value=PlanValue(content="虚构训练", distance_km=distance, main_type=kind),
    )


def candidate(plan_id: int = 10, *, kind: str = "easy", distance: float = 8):
    return ProposalCandidateChange(
        plan_id=plan_id,
        action=PlanAdjustmentAction.reduce,
        after=PlanValue(content="虚构减量训练", distance_km=distance, main_type=kind),
        reason="依据确定性周事实保守调整。",
        rule_evidence=["NO_MATERIAL_WEEKLY_DEVIATION"],
    )


def test_creates_reviewable_proposal_without_database_write() -> None:
    result = AdaptivePlanProposalService().create_proposal(
        user_id=7,
        weekly_facts=facts(),
        target_plans=[target()],
        candidates=[candidate()],
    )
    assert result.status.value == "PENDING_APPROVAL"
    assert result.changes[0].before.distance_km == 10
    assert result.changes[0].after.distance_km == 8
    assert "user_id" not in result.model_dump(mode="json")


def test_rejects_cross_user_target() -> None:
    other = target()
    other.user_id = 8
    with pytest.raises(BadRequestError):
        AdaptivePlanProposalService().create_proposal(
            user_id=7, weekly_facts=facts(), target_plans=[other], candidates=[]
        )


def test_insufficient_data_cannot_produce_deterministic_change() -> None:
    with pytest.raises(BadRequestError):
        AdaptivePlanProposalService().create_proposal(
            user_id=7,
            weekly_facts=facts(with_data=False),
            target_plans=[target()],
            candidates=[candidate()],
        )


def test_high_fatigue_blocks_volume_or_intensity_increase() -> None:
    increasing = candidate(kind="tempo", distance=12)
    with pytest.raises(BadRequestError):
        AdaptivePlanProposalService().create_proposal(
            user_id=7,
            weekly_facts=facts(fatigue="HIGH"),
            target_plans=[target()],
            candidates=[increasing],
        )


def test_locked_or_completed_plan_cannot_be_changed() -> None:
    locked = target()
    locked.is_locked = True
    with pytest.raises(BadRequestError):
        AdaptivePlanProposalService().create_proposal(
            user_id=7,
            weekly_facts=facts(),
            target_plans=[locked],
            candidates=[candidate()],
        )


def test_consecutive_high_intensity_days_are_rejected() -> None:
    first = target(10, kind="tempo", distance=8)
    second = target(11, kind="interval_speed", distance=6)
    second.workout_date = date(2026, 7, 14)
    with pytest.raises(BadRequestError):
        AdaptivePlanProposalService().create_proposal(
            user_id=7,
            weekly_facts=facts(),
            target_plans=[first, second],
            candidates=[],
        )
