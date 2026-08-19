from datetime import timedelta
from types import SimpleNamespace

from planner_core.database.models import PlannedWorkout, WorkoutLog
from planner_core.enums import WorkoutStatusNormalized
from server.services.weekly_review_ai_service import (
    _filter_adjustable_candidates,
    _is_adjustable_target_workout,
)
from server.services.weekly_review_stats_service import local_today


def workout(*, days_from_today: int, locked: bool = False, completed: bool = False):
    item = PlannedWorkout(
        workout_date=local_today() + timedelta(days=days_from_today),
        is_locked=locked,
    )
    if completed:
        item.workout_log = WorkoutLog(
            status_normalized=WorkoutStatusNormalized.completed_normal
        )
    return item


def test_only_future_unlocked_uncompleted_workouts_are_sent_to_plan_design():
    assert _is_adjustable_target_workout(workout(days_from_today=1)) is True
    assert _is_adjustable_target_workout(workout(days_from_today=-1)) is False
    assert _is_adjustable_target_workout(workout(days_from_today=1, locked=True)) is False
    assert _is_adjustable_target_workout(workout(days_from_today=1, completed=True)) is False


def test_materialize_ignores_candidate_outside_adjustable_plan():
    accepted, warnings = _filter_adjustable_candidates(
        [SimpleNamespace(plan_id=11), SimpleNamespace(plan_id=99)],
        [{"planned_workout_id": 11}],
    )
    assert [item.plan_id for item in accepted] == [11]
    assert warnings


def test_materialize_does_not_warn_for_valid_candidates():
    accepted, warnings = _filter_adjustable_candidates(
        [SimpleNamespace(plan_id=11)],
        [{"planned_workout_id": 11}],
    )
    assert [item.plan_id for item in accepted] == [11]
    assert warnings == []
