from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from planner_core.database.models import PlannedWorkout, WorkoutLog
from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.domain.runner_state_rules import RunnerStateRules
from server.schemas.runner_state import FatigueState, TrainingConsistencyState, VolumeTrendState
from server.services.runner_state_inference_service import RunnerStateInferenceService
from server.services.runner_state_rules_loader import (
    RunnerStateRulesConfigurationError,
    load_runner_state_rules,
)
from server.services.runner_state_service import build_runner_state_snapshot

RUNNER_ID = 301
END = date(2026, 1, 28)


def _row(
    item_id: int,
    day: date,
    *,
    distance: float | None = 5,
    rpe: int | float | None = None,
    workout_type: WorkoutMainTypeNormalized = WorkoutMainTypeNormalized.easy,
    planned: bool = False,
    status: WorkoutStatusNormalized = WorkoutStatusNormalized.completed_normal,
    session_index: int = 1,
):
    workout = PlannedWorkout(
        id=item_id,
        user_id=RUNNER_ID,
        cycle_id=1,
        block_id=1,
        workout_date=day,
        session_index=session_index,
        planned_content="Fictional training session",
        main_type_normalized=workout_type,
        sort_order=item_id,
    ) if planned else None
    log = WorkoutLog(
        id=item_id,
        user_id=RUNNER_ID,
        planned_workout_id=item_id if planned else None,
        activity_date=day,
        status_normalized=status,
        actual_distance_km=Decimal(str(distance)) if distance is not None else None,
        actual_duration_seconds=1800,
        rpe=rpe,
        workout_type=workout_type.value,
    )
    return (log, workout), workout


def _snapshot(rows, planned=None, *, end: date = END):
    return build_runner_state_snapshot(
        runner_id=RUNNER_ID,
        cycle=None,
        log_rows=rows,
        planned_workouts=planned or [],
        generated_at=datetime(end.year, end.month, end.day, 12, tzinfo=ZoneInfo("Asia/Shanghai")),
        timezone_name="Asia/Shanghai",
        calculation_window_end=end,
    )


def _volume_rows(recent_distance: float, *, baseline_distance: float = 30):
    rows = []
    # Six baseline sessions in three independent seven-day buckets.
    for index, offset in enumerate((27, 24, 20, 17, 13, 10), start=1):
        row, _ = _row(index, END - timedelta(days=offset), distance=baseline_distance / 6)
        rows.append(row)
    for index, offset in enumerate((3, 0), start=20):
        row, _ = _row(index, END - timedelta(days=offset), distance=recent_distance / 2)
        rows.append(row)
    return rows


def _frequency_rows(counts: list[int]):
    rows = []
    item_id = 1
    for week_index, count in enumerate(counts):
        for session in range(count):
            day = END - timedelta(days=27 - week_index * 7 - session)
            row, _ = _row(item_id, day)
            rows.append(row)
            item_id += 1
    return rows


@pytest.mark.parametrize(
    ("recent_distance", "expected"),
    [
        (5, VolumeTrendState.DECREASING),
        (7, VolumeTrendState.STABLE),
        (10, VolumeTrendState.STABLE),
        (12.5, VolumeTrendState.STABLE),
        (13, VolumeTrendState.INCREASING),
        (15, VolumeTrendState.INCREASING),
        (16, VolumeTrendState.SPIKING),
    ],
)
def test_volume_trend_threshold_states(recent_distance, expected):
    snapshot = _snapshot(_volume_rows(recent_distance))

    assert snapshot.volume_trend.state is expected
    assert snapshot.volume_trend.volume_ratio == recent_distance / 10
    assert snapshot.inferred_state.load_trend.value == "UNKNOWN"


def test_independent_previous_21d_window_boundaries_cross_month_and_year():
    rows = _volume_rows(10)
    outside, _ = _row(90, date(2025, 12, 31), distance=100)
    recent_start, _ = _row(91, date(2026, 1, 22), distance=1)
    rows.extend((outside, recent_start))

    snapshot = _snapshot(rows)

    assert snapshot.derived_metrics.calculation_window_start_previous_21d == date(2026, 1, 1)
    assert snapshot.derived_metrics.calculation_window_end_previous_21d == date(2026, 1, 21)
    assert snapshot.derived_metrics.distance_previous_21d_km == 30
    assert snapshot.recent_training.distance_7d_km == 11


def test_volume_trend_is_unknown_for_zero_or_insufficient_baseline():
    zero = _snapshot(_volume_rows(10, baseline_distance=0))
    insufficient = _snapshot(_volume_rows(10)[:2] + _volume_rows(10)[6:])

    assert zero.volume_trend.state is VolumeTrendState.UNKNOWN
    assert zero.volume_trend.volume_ratio is None
    assert insufficient.volume_trend.state is VolumeTrendState.UNKNOWN
    assert "INSUFFICIENT_BASELINE_DATA" in [item.value for item in insufficient.volume_trend.reason_codes]


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ([2, 2, 2, 2], TrainingConsistencyState.HIGH),
        ([1, 2, 1, 2], TrainingConsistencyState.MODERATE),
        ([1, 0, 1, 4], TrainingConsistencyState.LOW),
    ],
)
def test_consistency_falls_back_to_activity_regularity(counts, expected):
    snapshot = _snapshot(_frequency_rows(counts))

    assert snapshot.training_consistency.state is expected
    assert snapshot.training_consistency.basis.value == "ACTIVITY_REGULARITY"
    assert snapshot.recent_training.completion_rate_28d is None


def test_consistency_prefers_plan_completion_and_keeps_zero_plan_rate_null():
    rows = []
    planned = []
    for item_id, offset in enumerate((27, 24, 20, 17, 13, 10, 6, 0), start=1):
        row, workout = _row(item_id, END - timedelta(days=offset), planned=True)
        rows.append(row)
        planned.append(workout)
    snapshot = _snapshot(rows, planned)
    no_plan = _snapshot(_frequency_rows([2, 2, 2, 2]))

    assert snapshot.training_consistency.state is TrainingConsistencyState.HIGH
    assert snapshot.training_consistency.basis.value == "PLAN_COMPLETION"
    assert no_plan.recent_training.completion_rate_28d is None


@pytest.mark.parametrize(
    ("completed_offsets", "expected"),
    [
        ((27, 20, 13, 10, 6), TrainingConsistencyState.MODERATE),
        ((27, 20, 6), TrainingConsistencyState.LOW),
    ],
)
def test_plan_completion_consistency_moderate_and_low(completed_offsets, expected):
    planned = []
    rows = []
    plan_offsets = (27, 24, 20, 17, 13, 10, 6, 0)
    for item_id, offset in enumerate(plan_offsets, start=1):
        row, workout = _row(item_id, END - timedelta(days=offset), planned=True)
        planned.append(workout)
        if offset in completed_offsets:
            rows.append(row)
    # Preserve sufficient objective history without changing planned completion.
    for item_id, offset in enumerate((26, 18, 12, 5), start=30):
        row, _ = _row(item_id, END - timedelta(days=offset))
        rows.append(row)

    snapshot = _snapshot(rows, planned)

    assert snapshot.training_consistency.state is expected
    assert snapshot.training_consistency.basis.value == "PLAN_COMPLETION"


def test_rpe_coverage_skips_rule_and_exact_deltas_score_one_or_two():
    rows = _volume_rows(10)
    for row in rows:
        row[0].rpe = None
    insufficient = _snapshot(rows)

    rows_half = _volume_rows(10)
    for row in rows_half[:6]:
        row[0].rpe = 4
    for row in rows_half[6:]:
        row[0].rpe = 4.5
    moderate = _snapshot(rows_half)

    rows_high = _volume_rows(10)
    for row in rows_high[:6]:
        row[0].rpe = 4
    for row in rows_high[6:]:
        row[0].rpe = 5
    high = _snapshot(rows_high)

    assert "RPE_CHANGE" in insufficient.fatigue.skipped_signals
    assert "RPE_CHANGE" in moderate.fatigue.triggered_signals
    assert moderate.fatigue.score == 1
    assert high.fatigue.score == 2


def test_completion_drop_is_scored_only_with_two_valid_plan_windows():
    rows = []
    planned = []
    item_id = 1
    for offset in (27, 24, 20, 17, 13, 10):
        row, workout = _row(item_id, END - timedelta(days=offset), planned=True)
        rows.append(row)
        planned.append(workout)
        item_id += 1
    for offset in (6, 4, 2, 0):
        row, workout = _row(item_id, END - timedelta(days=offset), planned=True)
        planned.append(workout)
        if offset in (6, 4):
            rows.append(row)
        item_id += 1

    snapshot = _snapshot(rows, planned)

    assert snapshot.derived_metrics.completion_rate_previous_21d == 1
    assert snapshot.recent_training.completion_rate_7d == 0.5
    assert "PLAN_COMPLETION_CHANGE" in snapshot.fatigue.triggered_signals


def test_high_intensity_rules_exclude_long_run_and_collapse_same_day_for_streak():
    rows = _volume_rows(10)
    long_run, _ = _row(60, END, workout_type=WorkoutMainTypeNormalized.long_run, session_index=1)
    first, _ = _row(61, END - timedelta(days=1), workout_type=WorkoutMainTypeNormalized.interval_speed, session_index=1)
    second, _ = _row(62, END - timedelta(days=1), workout_type=WorkoutMainTypeNormalized.tempo, session_index=2)
    rows.extend((long_run, first, second))

    snapshot = _snapshot(rows)

    assert snapshot.derived_metrics.high_intensity_sessions_7d == 2
    assert snapshot.derived_metrics.maximum_consecutive_high_intensity_days_7d == 1


def test_consecutive_and_frequent_high_intensity_signals_and_risk_evidence():
    rows = _volume_rows(16)
    for item_id, offset in enumerate((2, 1, 0), start=70):
        row, _ = _row(item_id, END - timedelta(days=offset), workout_type=WorkoutMainTypeNormalized.interval_speed)
        rows.append(row)
    snapshot = _snapshot(rows)
    flags = {item.code.value: item for item in snapshot.risk_flags}

    assert snapshot.derived_metrics.maximum_consecutive_high_intensity_days_7d == 3
    assert snapshot.derived_metrics.high_intensity_sessions_7d == 3
    assert snapshot.fatigue.state is FatigueState.HIGH
    assert "CONSECUTIVE_HIGH_INTENSITY_DAYS" in flags
    assert "FREQUENT_HIGH_INTENSITY_SESSIONS" in flags
    assert all(flag.evidence and flag.evidence[0].source for flag in flags.values())


def test_fatigue_normal_elevated_high_and_unknown_signal_coverage():
    normal = _snapshot(_volume_rows(10))

    elevated_rows = _volume_rows(13)
    for row in elevated_rows[:6]:
        row[0].rpe = 4
    for row in elevated_rows[6:]:
        row[0].rpe = 4.5
    elevated = _snapshot(elevated_rows)

    high_rows = _volume_rows(16)
    for item_id, offset in enumerate((1, 0), start=90):
        row, _ = _row(item_id, END - timedelta(days=offset), workout_type=WorkoutMainTypeNormalized.interval_speed)
        high_rows.append(row)
    high = _snapshot(high_rows)
    unknown = _snapshot([])

    assert normal.fatigue.state is FatigueState.NORMAL
    assert elevated.fatigue.state is FatigueState.ELEVATED
    assert high.fatigue.state is FatigueState.HIGH
    assert unknown.fatigue.state is FatigueState.UNKNOWN
    assert unknown.fatigue.available_signal_count < 3


def test_reserved_states_phase_and_outputs_remain_uninferred():
    snapshot = _snapshot(_volume_rows(10))

    assert snapshot.inferred_state.training_phase.value == "UNKNOWN"
    assert snapshot.inferred_state.fitness_state.value == "UNKNOWN"
    assert snapshot.inferred_state.load_trend.value == "UNKNOWN"
    assert snapshot.inferred_state.weaknesses == []
    assert snapshot.inference_metadata.ruleset_version == "runner-state-rules-1.0.0"


def test_rules_are_validated_and_changing_config_changes_deterministic_result(tmp_path: Path):
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("version: bad\n", encoding="utf-8")
    with pytest.raises(RunnerStateRulesConfigurationError):
        load_runner_state_rules(invalid)

    snapshot = _snapshot(_volume_rows(13))
    rules = load_runner_state_rules()
    changed = RunnerStateRules.model_validate({
        **rules.model_dump(),
        "volume_trend": {**rules.volume_trend.model_dump(), "stable_upper": 1.4},
    })
    result_one = RunnerStateInferenceService(changed).infer(
        snapshot,
        log_rows=_volume_rows(13),
        planned_workouts=[],
        cycle=None,
    )
    result_two = RunnerStateInferenceService(changed).infer(
        snapshot,
        log_rows=_volume_rows(13),
        planned_workouts=[],
        cycle=None,
    )

    assert snapshot.volume_trend.state is VolumeTrendState.INCREASING
    assert result_one.volume_trend.state is VolumeTrendState.STABLE
    assert result_one.model_dump() == result_two.model_dump()


def test_inference_does_not_modify_plans_and_uses_no_medical_diagnostic_wording():
    rows = _volume_rows(16)
    plan = PlannedWorkout(
        id=800,
        user_id=RUNNER_ID,
        cycle_id=1,
        block_id=1,
        workout_date=END,
        session_index=1,
        planned_content="Untouched fictional plan",
        main_type_normalized=WorkoutMainTypeNormalized.easy,
        sort_order=1,
    )
    before = plan.planned_content
    snapshot = _snapshot(rows, [plan])
    serialized = snapshot.model_dump_json()

    assert plan.planned_content == before
    assert "诊断" not in serialized
    assert "疾病" not in serialized
