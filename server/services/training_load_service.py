from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin, PlannedWorkout, WorkoutLog
from planner_core.enums import (
    PlannedWorkoutLifecycleStatus,
    WorkoutMainTypeNormalized,
    WorkoutStatusNormalized,
)
from planner_core.utils.excel_parse import normalize_workout_main_type
from server.common.exceptions import BadRequestError
from server.domain import readiness_thresholds as thresholds
from server.domain.review_thresholds import HIGH_INTENSITY_TYPES, KEY_WORKOUT_TYPES
from server.schemas.training_readiness import DailyTrainingLoadRead, TrainingLoadSummaryRead
from server.schemas.training_read import (
    RecentTrainingRead,
    RecentTrainingSessionRead,
    TrainingDataQualityRead,
)
from server.services.weekly_review_stats_service import COMPLETED_STATUSES, REST_STATUSES, local_today

MAX_TREND_RANGE_DAYS = 120
EASY_TYPES = {WorkoutMainTypeNormalized.easy.value, WorkoutMainTypeNormalized.recovery.value}
MODERATE_TYPES = {
    WorkoutMainTypeNormalized.easy_with_speed.value,
    WorkoutMainTypeNormalized.long_run.value,
    WorkoutMainTypeNormalized.mixed.value,
}


def _float(value: Decimal | int | float | None) -> float:
    return round(float(value or 0), 4)


def _duration_minutes(seconds: int | None) -> float | None:
    if seconds is None:
        return None
    return round(seconds / 60, 4)


def session_srpe_load(duration_seconds: int | None, rpe: int | None, status: WorkoutStatusNormalized) -> float | None:
    if status in REST_STATUSES:
        return 0.0
    minutes = _duration_minutes(duration_seconds)
    if minutes is None or rpe is None:
        return None
    if minutes < 0:
        raise BadRequestError("Training duration cannot be negative.")
    if rpe < 0 or rpe > 10:
        raise BadRequestError("RPE must be between 0 and 10.")
    return round(minutes * rpe, 2)


def _high_intensity_distance(log: WorkoutLog, workout_type: str) -> float:
    effective = sum(
        _float(value)
        for value in (
            log.i_effective_km,
            log.t1_effective_km,
            log.t2_effective_km,
            log.r_effective_km,
        )
    )
    if effective > 0:
        return effective
    return _float(log.actual_distance_km) if workout_type in HIGH_INTENSITY_TYPES else 0.0


def _query_logs(db: Session, user_id: int, start_date: date, end_date: date) -> list[tuple[WorkoutLog, PlannedWorkout | None]]:
    return list(
        db.execute(
            select(WorkoutLog, PlannedWorkout)
            .outerjoin(PlannedWorkout, PlannedWorkout.id == WorkoutLog.planned_workout_id)
            .where(
                WorkoutLog.user_id == user_id,
                (PlannedWorkout.user_id == user_id) | (PlannedWorkout.id.is_(None)),
                func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date) >= start_date,
                func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date) <= end_date,
                func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date) <= local_today(),
            )
            .order_by(func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date), PlannedWorkout.sort_order, WorkoutLog.id)
        )
    )


def _safe_source(value: str | None) -> str:
    normalized = (value or "manual").strip().lower()
    if normalized.startswith("garmin"):
        return "GARMIN"
    if "import" in normalized:
        return "IMPORT"
    return "MANUAL"


def _brief_review(value: str | None, max_chars: int = 240) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    return cleaned[:max_chars] or None


def get_recent_training_read(
    db: Session,
    *,
    user_id: int,
    days: int,
    limit: int,
    as_of_date: date | None = None,
) -> RecentTrainingRead:
    """Return bounded, normalized training facts using the shared log query."""
    end_date = as_of_date or local_today()
    start_date = end_date - timedelta(days=days - 1)
    rows = _query_logs(db, user_id, start_date, end_date)
    sessions: list[RecentTrainingSessionRead] = []
    distances: list[float] = []
    completed_key_sessions = 0
    for log, workout in reversed(rows):
        workout_date = workout.workout_date if workout else log.activity_date
        if workout_date is None:
            continue
        workout_type = (
            workout.main_type_normalized.value
            if workout is not None
            else normalize_workout_main_type(log.workout_type).value
        )
        distance = float(log.actual_distance_km) if log.actual_distance_km is not None else None
        if distance is not None:
            distances.append(distance)
        is_completed_key = (
            log.status_normalized in COMPLETED_STATUSES and workout_type in KEY_WORKOUT_TYPES
        )
        completed_key_sessions += int(is_completed_key)
        sessions.append(
            RecentTrainingSessionRead(
                date=workout_date,
                training_type=workout_type,
                planned_or_unplanned=("UNPLANNED" if log.is_unplanned or workout is None else "PLANNED"),
                completion_status=log.status_normalized.value,
                distance_km=round(distance, 2) if distance is not None else None,
                duration_seconds=log.actual_duration_seconds,
                average_pace_seconds_per_km=log.avg_pace_seconds_per_km,
                average_heart_rate=log.avg_heart_rate,
                rpe=log.rpe if log.rpe is not None and 0 <= log.rpe <= 10 else None,
                source=_safe_source(log.source_type),
                brief_review=_brief_review(log.review_note),
                is_key_session=is_completed_key,
            )
        )
    rest_days = int(
        db.scalar(
            select(func.count(func.distinct(PlannedWorkout.workout_date))).where(
                PlannedWorkout.user_id == user_id,
                PlannedWorkout.workout_date >= start_date,
                PlannedWorkout.workout_date <= end_date,
                PlannedWorkout.main_type_normalized
                == WorkoutMainTypeNormalized.rest,
                PlannedWorkout.lifecycle_status == PlannedWorkoutLifecycleStatus.planned,
            )
        )
        or 0
    )
    return RecentTrainingRead(
        as_of_date=end_date,
        window_days=days,
        items=sessions[:limit],
        total_sessions=len(sessions),
        total_distance_km=round(sum(distances), 2) if distances else None,
        completed_key_sessions=completed_key_sessions,
        rest_days=rest_days,
    )


def get_training_data_quality_read(
    db: Session,
    *,
    user_id: int,
    window_days: int,
    as_of_date: date | None = None,
) -> TrainingDataQualityRead:
    """Describe field coverage; coverage is completeness, never risk probability."""
    end_date = as_of_date or local_today()
    start_date = end_date - timedelta(days=window_days - 1)
    completed = [
        log
        for log, _ in _query_logs(db, user_id, start_date, end_date)
        if log.status_normalized in COMPLETED_STATUSES
    ]
    total = len(completed)

    def ratio(predicate) -> float:
        return round(sum(1 for log in completed if predicate(log)) / total, 4) if total else 0.0

    coverage = {
        "distance": ratio(lambda log: log.actual_distance_km is not None),
        "duration": ratio(lambda log: log.actual_duration_seconds is not None),
        "rpe": ratio(lambda log: log.rpe is not None and 0 <= log.rpe <= 10),
        "heart_rate": ratio(lambda log: log.avg_heart_rate is not None),
    }
    missing = [name for name, value in coverage.items() if value < 1.0]
    source_mix: dict[str, int] = defaultdict(int)
    for log in completed:
        source_mix[_safe_source(log.source_type)] += 1
    dated = [log.activity_date for log in completed if log.activity_date is not None]
    return TrainingDataQualityRead(
        as_of_date=end_date,
        window_days=window_days,
        valid_workout_count=total,
        coverage=coverage,
        missing_fields=missing,
        source_mix=dict(sorted(source_mix.items())),
        freshness_days=(end_date - max(dated)).days if dated else None,
    )


def build_daily_training_loads(
    db: Session, user_id: int, start_date: date, end_date: date
) -> list[DailyTrainingLoadRead]:
    if end_date < start_date:
        raise BadRequestError("end_date must not be earlier than start_date.")
    if (end_date - start_date).days > MAX_TREND_RANGE_DAYS:
        raise BadRequestError("Date range is too large.")
    by_day: dict[date, dict] = {
        start_date + timedelta(days=offset): {
            "distance_km": 0.0,
            "duration_minutes": 0.0,
            "srpe_values": [],
            "easy_distance_km": 0.0,
            "moderate_distance_km": 0.0,
            "high_intensity_distance_km": 0.0,
            "key_workout_count": 0,
            "training_session_count": 0,
        }
        for offset in range((end_date - start_date).days + 1)
    }
    for log, workout in _query_logs(db, user_id, start_date, end_date):
        log_date = workout.workout_date if workout and workout.workout_date else log.activity_date
        if log_date is None:
            continue
        status = log.status_normalized
        if status not in COMPLETED_STATUSES and status not in REST_STATUSES:
            continue
        day = by_day[log_date]
        workout_type = workout.main_type_normalized.value if workout else normalize_workout_main_type(log.workout_type).value
        distance = _float(log.actual_distance_km)
        duration = _duration_minutes(log.actual_duration_seconds) or 0.0
        srpe = session_srpe_load(log.actual_duration_seconds, log.rpe, status)
        day["distance_km"] += distance
        day["duration_minutes"] += duration
        if srpe is not None:
            day["srpe_values"].append(srpe)
        if workout_type in EASY_TYPES:
            day["easy_distance_km"] += distance
        elif workout_type in HIGH_INTENSITY_TYPES:
            day["high_intensity_distance_km"] += _high_intensity_distance(log, workout_type)
        elif workout_type in MODERATE_TYPES:
            day["moderate_distance_km"] += distance
        if workout_type in KEY_WORKOUT_TYPES and status in COMPLETED_STATUSES:
            day["key_workout_count"] += 1
        if status in COMPLETED_STATUSES:
            day["training_session_count"] += 1
    return [
        DailyTrainingLoadRead(
            load_date=load_date,
            distance_km=round(values["distance_km"], 2),
            duration_minutes=round(values["duration_minutes"], 1),
            srpe_load_au=round(sum(values["srpe_values"]), 2) if values["srpe_values"] else None,
            easy_distance_km=round(values["easy_distance_km"], 2),
            moderate_distance_km=round(values["moderate_distance_km"], 2),
            high_intensity_distance_km=round(values["high_intensity_distance_km"], 2),
            key_workout_count=values["key_workout_count"],
            training_session_count=values["training_session_count"],
        )
        for load_date, values in sorted(by_day.items())
    ]


def _sum_optional(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return round(sum(valid), 2) if valid else None


def _safe_change(recent: float | None, baseline: float | None) -> tuple[float | None, float | None]:
    if recent is None or baseline is None or baseline <= 0:
        return None, None
    ratio = round(recent / baseline, 4)
    return ratio, round((recent - baseline) / baseline * 100, 1)


def _completed_log_counts(log_rows: list[tuple[WorkoutLog, PlannedWorkout | None]]) -> tuple[int, int]:
    completed = [
        log for log, _ in log_rows if log.status_normalized in COMPLETED_STATUSES
    ]
    valid_srpe = [
        log
        for log in completed
        if log.actual_duration_seconds is not None and log.rpe is not None
    ]
    return len(completed), len(valid_srpe)


def build_training_load_summary(db: Session, user_id: int, assessment_date: date | None = None) -> TrainingLoadSummaryRead:
    target_date = assessment_date or local_today()
    if target_date > local_today():
        raise BadRequestError("Assessment date cannot be in the future.")
    rolling_start = target_date - timedelta(days=thresholds.ROLLING_7D_DAYS - 1)
    baseline_start = target_date - timedelta(days=thresholds.BASELINE_28D_DAYS - 1)
    baseline_daily = build_daily_training_loads(db, user_id, baseline_start, target_date)
    rolling_daily = [item for item in baseline_daily if item.load_date >= rolling_start]

    rolling_srpe = _sum_optional([item.srpe_load_au for item in rolling_daily])
    baseline_srpe_total = _sum_optional([item.srpe_load_au for item in baseline_daily])
    baseline_srpe_weekly = round(baseline_srpe_total / 4, 2) if baseline_srpe_total is not None else None
    recent_to_baseline, load_change = _safe_change(rolling_srpe, baseline_srpe_weekly)

    rolling_distance = round(sum(item.distance_km for item in rolling_daily), 2)
    baseline_distance_total = round(sum(item.distance_km for item in baseline_daily), 2)
    baseline_distance_weekly = round(baseline_distance_total / 4, 2)
    _, distance_change = _safe_change(rolling_distance, baseline_distance_weekly)

    log_rows = _query_logs(db, user_id, baseline_start, target_date)
    completed_count, valid_srpe_count = _completed_log_counts(log_rows)
    rpe_values = [
        float(log.rpe)
        for log, _ in log_rows
        if log.status_normalized in COMPLETED_STATUSES and log.rpe is not None
    ]
    recovery_count = int(
        db.scalar(
            select(func.count()).select_from(DailyRecoveryCheckin).where(
                DailyRecoveryCheckin.user_id == user_id,
                DailyRecoveryCheckin.checkin_date >= rolling_start,
                DailyRecoveryCheckin.checkin_date <= target_date,
            )
        )
        or 0
    )
    first_log_date = db.scalar(
        select(func.min(func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date)))
        .select_from(WorkoutLog)
        .outerjoin(PlannedWorkout, PlannedWorkout.id == WorkoutLog.planned_workout_id)
        .where(
            WorkoutLog.user_id == user_id,
            func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date) <= target_date,
        )
    )
    history_days = (target_date - first_log_date).days + 1 if first_log_date else 0
    missing = []
    if completed_count == 0:
        missing.append("training_logs")
    if valid_srpe_count < completed_count:
        missing.append("duration_or_rpe")
    if recovery_count == 0:
        missing.append("recovery_checkins")

    return TrainingLoadSummaryRead(
        assessment_date=target_date,
        rolling_7d_distance_km=rolling_distance,
        rolling_7d_duration_minutes=round(sum(item.duration_minutes for item in rolling_daily), 1),
        rolling_7d_srpe_load_au=rolling_srpe,
        rolling_7d_high_intensity_distance_km=round(
            sum(item.high_intensity_distance_km for item in rolling_daily), 2
        ),
        rolling_7d_key_workout_count=sum(item.key_workout_count for item in rolling_daily),
        rolling_7d_training_session_count=sum(item.training_session_count for item in rolling_daily),
        baseline_28d_total_distance_km=baseline_distance_total,
        baseline_28d_weekly_distance_km=baseline_distance_weekly,
        baseline_28d_total_srpe_load_au=baseline_srpe_total,
        baseline_28d_weekly_srpe_load_au=baseline_srpe_weekly,
        baseline_28d_avg_rpe=round(sum(rpe_values) / len(rpe_values), 2) if rpe_values else None,
        srpe_coverage_ratio=round(valid_srpe_count / completed_count, 4) if completed_count else 0,
        recovery_checkin_coverage_ratio=round(recovery_count / thresholds.ROLLING_7D_DAYS, 4),
        recent_to_baseline_load_ratio=recent_to_baseline,
        load_change_percentage=load_change,
        distance_change_percentage=distance_change,
        history_days=history_days,
        missing_data=missing,
    )
