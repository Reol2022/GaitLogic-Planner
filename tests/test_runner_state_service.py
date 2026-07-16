from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from planner_core.database.models import (
    ExternalActivity,
    PlannedWorkout,
    TrainingCycle,
    WorkoutLog,
    WorkoutLogExternalActivity,
)
from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.services.garmin_sync_service import _fill_objective_log_fields
from server.services.runner_state_service import build_runner_state_snapshot

RUNNER_ID = 41
AS_OF = date(2026, 1, 5)


def _generated(day: date = AS_OF, timezone_name: str = "Asia/Shanghai") -> datetime:
    return datetime(day.year, day.month, day.day, 12, tzinfo=ZoneInfo(timezone_name))


def _row(
    item_id: int,
    day: date,
    *,
    workout_type: WorkoutMainTypeNormalized = WorkoutMainTypeNormalized.easy,
    status: WorkoutStatusNormalized = WorkoutStatusNormalized.completed_normal,
    distance: float | None = 5,
    duration_seconds: int | None = 1800,
    rpe: int | None = 5,
    heart_rate: int | None = 145,
    planned: bool = True,
) -> tuple[tuple[WorkoutLog, PlannedWorkout | None], PlannedWorkout | None]:
    workout = None
    if planned:
        workout = PlannedWorkout(
            id=item_id,
            user_id=RUNNER_ID,
            cycle_id=1,
            block_id=1,
            workout_date=day,
            session_index=1,
            planned_content=f"{workout_type.value} session",
            main_type_normalized=workout_type,
            sort_order=item_id,
        )
    log = WorkoutLog(
        id=item_id,
        user_id=RUNNER_ID,
        planned_workout_id=workout.id if workout else None,
        activity_date=day,
        status_normalized=status,
        actual_distance_km=Decimal(str(distance)) if distance is not None else None,
        actual_duration_seconds=duration_seconds,
        rpe=rpe,
        avg_heart_rate=heart_rate,
        workout_type=workout_type.value,
    )
    return (log, workout), workout


def _snapshot(
    rows: list[tuple[WorkoutLog, PlannedWorkout | None]],
    planned: list[PlannedWorkout] | None = None,
    *,
    day: date = AS_OF,
    cycle: TrainingCycle | None = None,
    last_quality_date: date | None = None,
    timezone_name: str = "Asia/Shanghai",
):
    return build_runner_state_snapshot(
        runner_id=RUNNER_ID,
        cycle=cycle,
        log_rows=rows,
        planned_workouts=planned or [],
        generated_at=_generated(day, timezone_name),
        timezone_name=timezone_name,
        calculation_window_end=day,
        last_quality_date=last_quality_date,
    )


def test_empty_state_is_legal_and_inference_is_unknown():
    snapshot = _snapshot([])

    assert snapshot.recent_training.distance_7d_km is None
    assert snapshot.recent_training.sessions_28d == 0
    assert snapshot.recent_training.completion_rate_7d is None
    assert snapshot.data_quality.data_quality_level.value == "NONE"
    assert snapshot.data_quality.confidence == 0
    assert {
        snapshot.inferred_state.fitness_state.value,
        snapshot.inferred_state.fatigue_state.value,
        snapshot.inferred_state.load_trend.value,
        snapshot.inferred_state.training_consistency.value,
        snapshot.inferred_state.training_phase.value,
    } == {"UNKNOWN"}
    assert snapshot.inferred_state.risk_flags == []


def test_one_completed_session_uses_known_values_without_zero_filling():
    row, workout = _row(1, AS_OF, distance=10.25, duration_seconds=3660, rpe=6)
    snapshot = _snapshot([row], [workout])

    assert snapshot.recent_training.distance_7d_km == 10.25
    assert snapshot.recent_training.duration_7d_minutes == 61.0
    assert snapshot.recent_training.average_rpe_7d == 6
    assert snapshot.recent_training.completed_sessions_7d == 1


def test_complete_7d_and_28d_windows_are_inclusive_and_deterministic():
    rows = []
    planned = []
    for offset in range(28):
        row, workout = _row(offset + 1, AS_OF - timedelta(days=offset), distance=5)
        rows.append(row)
        planned.append(workout)

    snapshot = _snapshot(rows, planned)

    assert snapshot.recent_training.distance_7d_km == 35
    assert snapshot.recent_training.distance_28d_km == 140
    assert snapshot.recent_training.sessions_7d == 7
    assert snapshot.recent_training.sessions_28d == 28
    assert snapshot.recent_training.completion_rate_7d == 1
    assert snapshot.recent_training.completion_rate_28d == 1


def test_cross_month_and_cross_year_boundaries_exclude_day_29():
    inside_start, inside_workout = _row(1, date(2025, 12, 9), distance=4)
    inside_end, end_workout = _row(2, date(2026, 1, 5), distance=6)
    outside, outside_workout = _row(3, date(2025, 12, 8), distance=100)

    snapshot = _snapshot(
        [inside_start, inside_end, outside],
        [inside_workout, end_workout, outside_workout],
    )

    assert snapshot.identity.calculation_window_start_28d == date(2025, 12, 9)
    assert snapshot.recent_training.distance_28d_km == 10


def test_dst_timezone_uses_calendar_dates_not_fixed_string_offsets():
    snapshot = _snapshot([], day=date(2026, 3, 8), timezone_name="America/New_York")

    assert snapshot.identity.timezone == "America/New_York"
    assert snapshot.identity.calculation_window_start_7d == date(2026, 3, 2)
    assert snapshot.identity.calculation_window_start_28d == date(2026, 2, 9)


def test_missing_partial_and_invalid_rpe_and_heart_rate_are_reported():
    first, first_plan = _row(1, AS_OF, rpe=4, heart_rate=140)
    second, second_plan = _row(2, AS_OF - timedelta(days=1), rpe=None, heart_rate=None)
    invalid, invalid_plan = _row(3, AS_OF - timedelta(days=2), rpe=11, heart_rate=None)

    snapshot = _snapshot([first, second, invalid], [first_plan, second_plan, invalid_plan])

    assert snapshot.recent_training.average_rpe_7d == 4
    assert snapshot.data_quality.rpe_coverage_7d == pytest.approx(1 / 3, abs=0.0001)
    assert snapshot.data_quality.heart_rate_coverage_7d == pytest.approx(1 / 3, abs=0.0001)
    assert "invalid_rpe_excluded:1" in snapshot.data_quality.limitations


def test_no_plan_returns_null_completion_rate():
    row, _ = _row(1, AS_OF, planned=False)
    snapshot = _snapshot([row])

    assert snapshot.recent_training.planned_sessions_7d == 0
    assert snapshot.recent_training.completion_rate_7d is None
    assert "completion_rate_7d_unavailable_no_planned_sessions" in snapshot.data_quality.limitations


def test_mixed_completed_and_uncompleted_plans_use_session_completion_formula():
    completed, completed_plan = _row(1, AS_OF)
    missed, missed_plan = _row(2, AS_OF - timedelta(days=1), status=WorkoutStatusNormalized.missed)
    _, no_log_plan = _row(3, AS_OF - timedelta(days=2))

    snapshot = _snapshot([completed, missed], [completed_plan, missed_plan, no_log_plan])

    assert snapshot.recent_training.planned_sessions_7d == 3
    assert snapshot.recent_training.completed_sessions_7d == 1
    assert snapshot.recent_training.completion_rate_7d == pytest.approx(1 / 3, abs=0.0001)


def test_intensity_uses_existing_main_types_and_tracks_composite_limitation():
    specs = [
        (WorkoutMainTypeNormalized.easy, 5),
        (WorkoutMainTypeNormalized.tempo, 10),
        (WorkoutMainTypeNormalized.long_run, 20),
        (WorkoutMainTypeNormalized.mixed, 8),
        (WorkoutMainTypeNormalized.unknown, 3),
    ]
    rows = []
    planned = []
    for item_id, (workout_type, distance) in enumerate(specs, start=1):
        row, workout = _row(item_id, AS_OF - timedelta(days=item_id - 1), workout_type=workout_type, distance=distance)
        rows.append(row)
        planned.append(workout)

    snapshot = _snapshot(rows, planned, last_quality_date=AS_OF - timedelta(days=2))

    assert snapshot.intensity.easy_distance_7d_km == 5
    assert snapshot.intensity.moderate_distance_7d_km == 28
    assert snapshot.intensity.hard_distance_7d_km == 10
    assert snapshot.intensity.hard_distance_ratio_7d == round(10 / 46, 4)
    assert snapshot.intensity.quality_sessions_7d == 2
    assert snapshot.intensity.long_run_distance_7d_km == 20
    assert snapshot.intensity.days_since_last_quality_session == 2
    assert "composite_workout_intensity_segments_not_split" in snapshot.data_quality.limitations
    assert "unclassified_workout_distance_excluded_from_intensity_buckets" in snapshot.data_quality.limitations


def test_duplicate_and_composite_activity_rows_count_canonical_log_once():
    row, workout = _row(1, AS_OF, distance=12)
    row[0].external_activity_links = [
        WorkoutLogExternalActivity(
            user_id=RUNNER_ID,
            workout_log_id=1,
            external_activity_id=101,
        ),
        WorkoutLogExternalActivity(
            user_id=RUNNER_ID,
            workout_log_id=1,
            external_activity_id=102,
        ),
    ]
    snapshot = _snapshot([row, row], [workout])

    assert snapshot.recent_training.sessions_7d == 1
    assert snapshot.recent_training.distance_7d_km == 12


def test_garmin_meter_distance_is_converted_by_existing_merge_logic():
    activity = ExternalActivity(distance_m=Decimal("5000"), duration_seconds=1800)
    log = WorkoutLog(user_id=RUNNER_ID, status_normalized=WorkoutStatusNormalized.completed_normal)

    _fill_objective_log_fields(log, activity)

    assert log.actual_distance_km == Decimal("5")
    row = (log, None)
    log.id = 99
    log.activity_date = AS_OF
    log.workout_type = WorkoutMainTypeNormalized.easy.value
    snapshot = _snapshot([row])
    assert snapshot.recent_training.distance_7d_km == 5


def test_goal_uses_only_structured_cycle_fields_and_strict_time_parsing():
    cycle = TrainingCycle(
        user_id=RUNNER_ID,
        name="Fictional cycle",
        target_race_name="Fictional city marathon",
        target_race_date=AS_OF + timedelta(days=70),
        target_result="03:30:00",
    )

    snapshot = _snapshot([], cycle=cycle)

    assert snapshot.goal_context.race_distance is None
    assert snapshot.goal_context.race_date == AS_OF + timedelta(days=70)
    assert snapshot.goal_context.target_time_seconds == 12600
    assert snapshot.goal_context.weeks_remaining == 10
