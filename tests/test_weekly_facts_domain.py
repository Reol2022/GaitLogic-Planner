from __future__ import annotations

from datetime import date
import json
from math import isfinite
from pathlib import Path

import pytest
from pydantic import ValidationError

from planner_core.weekly_review.aggregation import build_weekly_facts
from planner_core.weekly_review.enums import (
    DeviationType,
    WeeklyClassificationStatus,
    WeeklyDataQualityLevel,
)
from planner_core.weekly_review.schemas import (
    PlannedSessionFact,
    RunnerStateSampleFact,
    WeeklyFactsRequest,
    WeeklyPeriod,
    WorkoutSessionFact,
)


START = date(2026, 7, 6)
END = date(2026, 7, 12)


def plan(
    plan_id: int,
    day: int,
    kind: str = "easy",
    distance: float | None = 10,
) -> PlannedSessionFact:
    return PlannedSessionFact(
        plan_id=plan_id,
        session_date=date(2026, 7, day),
        main_type=kind,
        distance_km=distance,
    )


def log(
    log_id: int,
    day: int,
    plan_id: int | None = None,
    kind: str = "easy",
    distance: float | None = 10,
    *,
    sport: str = "running",
    fingerprint: str | None = None,
) -> WorkoutSessionFact:
    return WorkoutSessionFact(
        log_id=log_id,
        activity_date=date(2026, 7, day),
        planned_workout_id=plan_id,
        main_type=kind,
        distance_km=distance,
        duration_minutes=60,
        status="completed_normal",
        sport_type=sport,
        activity_fingerprint=fingerprint,
    )


def facts(
    plans: list[PlannedSessionFact],
    logs: list[WorkoutSessionFact],
    samples: list[RunnerStateSampleFact] | None = None,
    as_of: date = END,
):
    return build_weekly_facts(
        period=WeeklyPeriod(
            week_start=START,
            week_end=END,
            timezone="Asia/Shanghai",
        ),
        plans=plans,
        logs=logs,
        runner_state_samples=samples or [],
        as_of_date=as_of,
    )


def test_request_is_strict_and_validates_period_and_timezone() -> None:
    valid = WeeklyFactsRequest(
        user_id=1, week_start=START, week_end=END, timezone="Asia/Shanghai"
    )
    assert valid.week_start == START
    with pytest.raises(ValidationError):
        WeeklyFactsRequest(
            user_id=1,
            week_start=END,
            week_end=START,
            timezone="Asia/Shanghai",
        )
    with pytest.raises(ValidationError):
        WeeklyFactsRequest(
            user_id=1,
            week_start=START,
            week_end=END,
            timezone="Mars/Olympus",
        )
    with pytest.raises(ValidationError):
        WeeklyFactsRequest(
            user_id=1,
            week_start=START,
            week_end=END,
            timezone="Asia/Shanghai",
            provider="forbidden",
        )


def test_explicit_plan_match_and_basic_aggregation() -> None:
    result = facts([plan(1, 6)], [log(11, 6, 1)])
    assert result.planned.planned_running_session_count == 1
    assert result.completed.completed_running_session_count == 1
    assert result.adherence.session_completion_rate == 1
    assert result.adherence.distance_completion_rate == 1
    assert result.classification.primary_status == WeeklyClassificationStatus.ON_TRACK
    assert result.planned.planned_high_intensity_session_count == 0
    assert result.completed.partial_session_count == 0
    assert result.completed.missed_session_count == 0
    assert result.completed.extra_session_count == 0


def test_unique_date_and_type_match() -> None:
    result = facts([plan(1, 6)], [log(11, 6)])
    assert result.adherence.session_completion_rate == 1
    assert result.data_quality.unmatched_log_count == 0


def test_same_day_multiple_candidates_are_ambiguous() -> None:
    result = facts([plan(1, 6), plan(2, 6)], [log(11, 6)])
    assert result.data_quality.level == WeeklyDataQualityLevel.CONFLICTED
    assert result.data_quality.ambiguous_match_count == 1
    assert DeviationType.DUPLICATE_OR_AMBIGUOUS_LOG in {
        item.deviation_type for item in result.deviations
    }


def test_unmatched_log_is_extra_and_retained() -> None:
    result = facts([], [log(11, 6)])
    kinds = {item.deviation_type for item in result.deviations}
    assert DeviationType.UNMATCHED_LOG in kinds
    assert DeviationType.EXTRA_SESSION in kinds
    assert result.data_quality.unmatched_log_count == 1
    assert result.completed.extra_session_count == 1


def test_duplicate_fingerprint_is_not_double_counted() -> None:
    result = facts(
        [],
        [
            log(11, 6, fingerprint="fictional-activity"),
            log(12, 6, fingerprint="fictional-activity"),
        ],
    )
    assert result.completed.completed_session_count == 1
    assert result.data_quality.ambiguous_match_count == 1


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (7.9, DeviationType.DISTANCE_UNDER),
        (12.1, DeviationType.DISTANCE_OVER),
    ],
)
def test_distance_deviation(actual: float, expected: DeviationType) -> None:
    result = facts([plan(1, 6)], [log(11, 6, 1, distance=actual)])
    assert expected in {item.deviation_type for item in result.deviations}


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (35.0, DeviationType.DURATION_UNDER),
        (65.0, DeviationType.DURATION_OVER),
    ],
)
def test_duration_deviation(actual: float, expected: DeviationType) -> None:
    planned = plan(1, 6)
    planned.duration_minutes = 50.0
    completed = log(11, 6, 1)
    completed.duration_minutes = actual
    result = facts([planned], [completed])
    assert expected in {item.deviation_type for item in result.deviations}


def test_cancelled_plan_is_excluded_from_denominators() -> None:
    cancelled = plan(2, 7, "tempo")
    cancelled.is_cancelled = True
    result = facts(
        [plan(1, 6), cancelled],
        [log(11, 6, 1)],
    )
    assert result.planned.planned_running_session_count == 1
    assert result.adherence.session_completion_rate == 1.0
    assert DeviationType.KEY_SESSION_MISSED not in {
        item.deviation_type for item in result.deviations
    }


def test_logs_without_plan_keep_observed_domains_and_block_plan_adherence_only() -> None:
    result = facts([], [log(11, 6)])
    domains = {item["domain"]: item["readiness"] for item in result.classification.domain_readiness}
    assert result.classification.overall_readiness == "PARTIAL"
    assert domains["plan_execution"] == "BLOCKED"
    assert domains["training_volume"] == "READY"
    assert "COMPLETED_WITHOUT_PLAN" in result.classification.evidence_codes
    assert result.adherence.session_completion_rate is None
    assert result.data_quality.missing_plan_days == [date(2026, 7, 6)]


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("easy", DeviationType.MISSED_SESSION),
        ("tempo", DeviationType.KEY_SESSION_MISSED),
        ("long_run", DeviationType.LONG_RUN_MISSED),
    ],
)
def test_missed_session_types(kind: str, expected: DeviationType) -> None:
    result = facts([plan(1, 6, kind)], [])
    assert expected in {item.deviation_type for item in result.deviations}
    assert result.completed.missed_session_count == 1


def test_adjusted_completion_is_reported_as_partial_without_losing_completion() -> None:
    adjusted = log(11, 6, 1)
    adjusted.status = "completed_adjusted"
    result = facts([plan(1, 6, "tempo")], [adjusted])
    assert result.completed.completed_session_count == 1
    assert result.completed.partial_session_count == 1
    assert result.planned.planned_high_intensity_session_count == 1
    assert result.completed.completed_high_intensity_session_count == 1


def test_cross_month_period_is_deterministic() -> None:
    period = WeeklyPeriod(
        week_start=date(2026, 7, 30),
        week_end=date(2026, 8, 5),
        timezone="Asia/Shanghai",
    )
    planned = PlannedSessionFact(
        plan_id=1,
        session_date=date(2026, 8, 1),
        main_type="easy",
        distance_km=8,
    )
    completed = WorkoutSessionFact(
        log_id=1,
        activity_date=date(2026, 8, 1),
        planned_workout_id=1,
        main_type="easy",
        distance_km=8,
        duration_minutes=48,
        status="completed_normal",
    )
    first = build_weekly_facts(
        period=period,
        plans=[planned],
        logs=[completed],
        runner_state_samples=[],
        as_of_date=date(2026, 8, 5),
    )
    second = build_weekly_facts(
        period=period,
        plans=[planned],
        logs=[completed],
        runner_state_samples=[],
        as_of_date=date(2026, 8, 5),
    )
    assert first.period.week_start.month == 7
    assert first.period.week_end.month == 8
    assert first.result_hash == second.result_hash


def test_strength_does_not_add_running_distance() -> None:
    result = facts([], [log(11, 6, sport="strength", distance=5)])
    assert result.completed.actual_distance_km is None
    assert result.completed.completed_running_session_count == 0


def test_missing_distance_is_not_coerced_to_zero() -> None:
    result = facts([plan(1, 6, distance=None)], [log(11, 6, 1, distance=None)])
    assert result.planned.planned_distance_km is None
    assert result.completed.actual_distance_km is None
    assert result.adherence.distance_completion_rate is None


def test_rest_day_is_counted_separately() -> None:
    result = facts([plan(1, 6, "rest", 0)], [])
    assert result.planned.planned_rest_days == 1
    assert result.planned.planned_running_session_count == 0
    assert result.adherence.session_completion_rate is None


def test_future_day_is_excluded_from_completion() -> None:
    result = facts(
        [plan(1, 6), plan(2, 12)],
        [log(11, 6, 1)],
        as_of=date(2026, 7, 8),
    )
    assert result.planned.planned_running_session_count == 1
    assert result.adherence.session_completion_rate == 1


def test_intensity_distribution_uses_existing_main_types() -> None:
    result = facts(
        [plan(1, 6, "easy", 10), plan(2, 7, "tempo", 5), plan(3, 8, "long_run", 15)],
        [
            log(11, 6, 1, "easy", 10),
            log(12, 7, 2, "tempo", 5),
            log(13, 8, 3, "long_run", 15),
        ],
    )
    assert result.distribution.easy_distance_km == 10
    assert result.distribution.hard_distance_km == 5
    assert result.distribution.moderate_distance_km == 15
    assert result.distribution.hard_ratio == pytest.approx(0.1667)


def test_intensity_mismatch_classification() -> None:
    result = facts([plan(1, 6, "easy")], [log(11, 6, 1, "tempo")])
    assert (
        result.classification.primary_status
        == WeeklyClassificationStatus.INTENSITY_IMBALANCE
    )


@pytest.mark.parametrize(
    ("actual", "status"),
    [
        (7.0, WeeklyClassificationStatus.UNDER_COMPLETED),
        (13.0, WeeklyClassificationStatus.OVER_COMPLETED),
    ],
)
def test_volume_classification(actual: float, status: WeeklyClassificationStatus) -> None:
    result = facts([plan(1, 6)], [log(11, 6, 1, distance=actual)])
    assert result.classification.primary_status == status


def test_recovery_concern_only_uses_runner_state() -> None:
    samples = [
        RunnerStateSampleFact(sample_date=START, fatigue_state="NORMAL"),
        RunnerStateSampleFact(
            sample_date=END, fatigue_state="ELEVATED", risk_flag_count=1
        ),
    ]
    result = facts([plan(1, 6)], [log(11, 6, 1)], samples)
    assert (
        result.classification.primary_status
        == WeeklyClassificationStatus.RECOVERY_CONCERN
    )
    assert result.runner_state_trend.fatigue_trend == "INCREASING"


def test_insufficient_runner_state_history_is_explicit() -> None:
    result = facts([plan(1, 6)], [log(11, 6, 1)])
    assert "INSUFFICIENT_RUNNER_STATE_HISTORY" in result.classification.limitations
    assert result.runner_state_trend.sample_count == 0


def test_no_data_is_insufficient() -> None:
    result = facts([], [])
    assert result.data_quality.level == WeeklyDataQualityLevel.INSUFFICIENT
    assert (
        result.classification.primary_status
        == WeeklyClassificationStatus.INSUFFICIENT_DATA
    )


def test_hash_is_stable_and_generated_at_is_excluded() -> None:
    first = facts([plan(1, 6)], [log(11, 6, 1)])
    second = facts([plan(1, 6)], [log(11, 6, 1)])
    assert first.generated_at != second.generated_at or first.generated_at == second.generated_at
    assert first.result_hash == second.result_hash
    changed = facts([plan(1, 6)], [log(11, 6, 1, distance=9)])
    assert changed.result_hash != first.result_hash


def test_ratios_never_emit_nan_or_infinity() -> None:
    result = facts([], [])
    values = result.adherence.model_dump().values()
    assert all(value is None or isfinite(value) for value in values)


def test_domain_does_not_import_agent_rag_or_garmin() -> None:
    import inspect
    import planner_core.weekly_review.aggregation as module

    source = inspect.getsource(module)
    assert "server.agent" not in source
    assert "knowledge_retrieval" not in source
    assert "garmin" not in source.lower()


def test_public_fictional_case_catalog_has_at_least_30_unique_cases() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "evaluation"
        / "weekly_review"
        / "cases_v1.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    ids = [item["case_id"] for item in cases]
    assert len(cases) >= 30
    assert len(ids) == len(set(ids))
    assert "fictional" in payload["data_policy"].lower()
    assert {
        "on_track",
        "under_completed",
        "over_completed",
        "key_session_missed",
        "intensity_imbalance",
        "recovery_concern",
        "insufficient",
        "matching",
    }.issubset({item["category"] for item in cases})
