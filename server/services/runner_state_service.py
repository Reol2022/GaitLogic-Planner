from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from planner_core.database.models import PlannedWorkout, TrainingCycle, UserAccount, WorkoutLog
from planner_core.enums import PlannedWorkoutLifecycleStatus, WorkoutMainTypeNormalized
from planner_core.utils.excel_parse import normalize_workout_main_type
from server.domain.review_thresholds import HIGH_INTENSITY_TYPES, KEY_WORKOUT_TYPES
from server.schemas.runner_state import (
    DataQualityLevel,
    InferredStatePlaceholders,
    IntensityMetrics,
    RecentTrainingMetrics,
    RunnerGoalContext,
    RunnerIdentityReference,
    RunnerStateDataQuality,
    RunnerStateSnapshot,
)
from server.services import training_cycle_lifecycle_service
from server.services.training_load_service import EASY_TYPES, MODERATE_TYPES, _query_logs
from server.services.weekly_review_stats_service import APP_TIMEZONE, COMPLETED_STATUSES, REST_STATUSES

logger = logging.getLogger(__name__)

WINDOW_7D_DAYS = 7
WINDOW_28D_DAYS = 28
VALID_RPE_MIN = 0
VALID_RPE_MAX = 10
DATA_FIELDS = (
    "training_logs",
    "actual_distance_km",
    "actual_duration_seconds",
    "rpe",
    "heart_rate",
    "planned_workouts",
    "goal_context",
    "intensity_classification",
)


@dataclass(frozen=True)
class _WindowMetrics:
    distance_km: float | None
    duration_minutes: float | None
    sessions: int
    completed_sessions: int
    planned_sessions: int
    completed_planned_sessions: int
    average_rpe: float | None
    easy_distance_km: float | None
    moderate_distance_km: float | None
    hard_distance_km: float | None
    hard_distance_ratio: float | None
    quality_sessions: int
    long_run_distance_km: float | None
    valid_workout_count: int
    rpe_coverage: float
    heart_rate_coverage: float
    distance_coverage: float
    duration_coverage: float
    invalid_rpe_count: int
    invalid_distance_count: int
    invalid_duration_count: int
    composite_type_count: int
    unclassified_distance_count: int


def _rounded_sum(values: list[float], digits: int) -> float | None:
    return round(sum(values), digits) if values else None


def _valid_nonnegative(value: Decimal | int | float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if number >= 0 else None


def _effective_date(log: WorkoutLog, workout: PlannedWorkout | None) -> date | None:
    return workout.workout_date if workout and workout.workout_date else log.activity_date


def _effective_type(log: WorkoutLog, workout: PlannedWorkout | None) -> WorkoutMainTypeNormalized:
    if workout is not None:
        value = workout.main_type_normalized
        return value if isinstance(value, WorkoutMainTypeNormalized) else WorkoutMainTypeNormalized(value)
    return normalize_workout_main_type(log.workout_type)


def _deduplicate_log_rows(
    rows: list[tuple[WorkoutLog, PlannedWorkout | None]],
) -> list[tuple[WorkoutLog, PlannedWorkout | None]]:
    unique: list[tuple[WorkoutLog, PlannedWorkout | None]] = []
    seen: set[tuple[str, int]] = set()
    for log, workout in rows:
        key = ("database", int(log.id)) if log.id is not None else ("object", id(log))
        if key in seen:
            continue
        seen.add(key)
        unique.append((log, workout))
    return unique


def _window_metrics(
    rows: list[tuple[WorkoutLog, PlannedWorkout | None]],
    planned: list[PlannedWorkout],
    start: date,
    end: date,
) -> _WindowMetrics:
    window_rows = [row for row in rows if (day := _effective_date(*row)) is not None and start <= day <= end]
    window_planned = [item for item in planned if item.workout_date and start <= item.workout_date <= end and item.main_type_normalized != WorkoutMainTypeNormalized.rest]
    non_rest_rows = [row for row in window_rows if row[0].status_normalized not in REST_STATUSES and _effective_type(*row) != WorkoutMainTypeNormalized.rest]
    completed = [row for row in non_rest_rows if row[0].status_normalized in COMPLETED_STATUSES]

    completed_planned_ids = {
        int(workout.id)
        for log, workout in completed
        if workout is not None and workout.id is not None and log.status_normalized in COMPLETED_STATUSES
    }
    planned_ids = {int(item.id) for item in window_planned if item.id is not None}
    completed_planned_sessions = len(completed_planned_ids & planned_ids)

    distances: list[float] = []
    durations: list[float] = []
    rpes: list[float] = []
    easy: list[float] = []
    moderate: list[float] = []
    hard: list[float] = []
    long_runs: list[float] = []
    valid_workouts = 0
    heart_rate_count = 0
    invalid_rpe = 0
    invalid_distance = 0
    invalid_duration = 0
    composite_types = 0
    unclassified_distance = 0
    quality_sessions = 0

    for log, workout in completed:
        workout_type = _effective_type(log, workout)
        distance = _valid_nonnegative(log.actual_distance_km)
        duration_seconds = _valid_nonnegative(log.actual_duration_seconds)
        if log.actual_distance_km is not None and distance is None:
            invalid_distance += 1
        if log.actual_duration_seconds is not None and duration_seconds is None:
            invalid_duration += 1
        if distance is not None:
            distances.append(distance)
            if workout_type.value in EASY_TYPES:
                easy.append(distance)
            elif workout_type.value in HIGH_INTENSITY_TYPES:
                hard.append(distance)
            elif workout_type.value in MODERATE_TYPES:
                moderate.append(distance)
            else:
                unclassified_distance += 1
            if workout_type == WorkoutMainTypeNormalized.long_run:
                long_runs.append(distance)
            if workout_type in {WorkoutMainTypeNormalized.easy_with_speed, WorkoutMainTypeNormalized.mixed}:
                composite_types += 1
        if duration_seconds is not None:
            durations.append(duration_seconds / 60)
        if distance is not None or duration_seconds is not None:
            valid_workouts += 1
        if log.rpe is not None:
            if VALID_RPE_MIN <= log.rpe <= VALID_RPE_MAX:
                rpes.append(float(log.rpe))
            else:
                invalid_rpe += 1
        if log.avg_heart_rate is not None or log.max_heart_rate is not None:
            heart_rate_count += 1
        if workout_type.value in KEY_WORKOUT_TYPES:
            quality_sessions += 1

    completed_count = len(completed)
    total_distance = _rounded_sum(distances, 2)
    hard_distance = _rounded_sum(hard, 2)
    hard_ratio = round(hard_distance / total_distance, 4) if hard_distance is not None and total_distance and total_distance > 0 else None
    return _WindowMetrics(
        distance_km=total_distance,
        duration_minutes=_rounded_sum(durations, 1),
        sessions=len(non_rest_rows),
        completed_sessions=completed_count,
        planned_sessions=len(window_planned),
        completed_planned_sessions=completed_planned_sessions,
        average_rpe=round(mean(rpes), 2) if rpes else None,
        easy_distance_km=_rounded_sum(easy, 2),
        moderate_distance_km=_rounded_sum(moderate, 2),
        hard_distance_km=hard_distance,
        hard_distance_ratio=hard_ratio,
        quality_sessions=quality_sessions,
        long_run_distance_km=_rounded_sum(long_runs, 2),
        valid_workout_count=valid_workouts,
        rpe_coverage=round(len(rpes) / completed_count, 4) if completed_count else 0,
        heart_rate_coverage=round(heart_rate_count / completed_count, 4) if completed_count else 0,
        distance_coverage=round(len(distances) / completed_count, 4) if completed_count else 0,
        duration_coverage=round(len(durations) / completed_count, 4) if completed_count else 0,
        invalid_rpe_count=invalid_rpe,
        invalid_distance_count=invalid_distance,
        invalid_duration_count=invalid_duration,
        composite_type_count=composite_types,
        unclassified_distance_count=unclassified_distance,
    )


def _completion_rate(metrics: _WindowMetrics) -> float | None:
    if metrics.planned_sessions == 0:
        return None
    return round(metrics.completed_planned_sessions / metrics.planned_sessions, 4)


def _target_time_seconds(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip()
    match = re.fullmatch(r"(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)", text)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _goal_context(cycle: TrainingCycle | None, window_end: date) -> RunnerGoalContext:
    if cycle is None:
        return RunnerGoalContext()
    race_date = cycle.target_race_date
    weeks_remaining = None
    if race_date is not None:
        weeks_remaining = round(max((race_date - window_end).days, 0) / 7, 1)
    return RunnerGoalContext(
        race_distance=None,
        race_date=race_date,
        target_time_seconds=_target_time_seconds(cycle.target_result),
        weeks_remaining=weeks_remaining,
    )


def _quality_level(confidence: float, completed_count: int) -> DataQualityLevel:
    if completed_count == 0:
        return DataQualityLevel.NONE
    if confidence >= 0.8:
        return DataQualityLevel.HIGH
    if confidence >= 0.5:
        return DataQualityLevel.MEDIUM
    return DataQualityLevel.LOW


def build_runner_state_snapshot(
    *,
    runner_id: int,
    cycle: TrainingCycle | None,
    log_rows: list[tuple[WorkoutLog, PlannedWorkout | None]],
    planned_workouts: list[PlannedWorkout],
    generated_at: datetime,
    timezone_name: str,
    calculation_window_end: date | None = None,
    last_quality_date: date | None = None,
) -> RunnerStateSnapshot:
    zone = ZoneInfo(timezone_name)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=zone)
    else:
        generated_at = generated_at.astimezone(zone)
    window_end = calculation_window_end or generated_at.date()
    start_7d = window_end - timedelta(days=WINDOW_7D_DAYS - 1)
    start_28d = window_end - timedelta(days=WINDOW_28D_DAYS - 1)
    rows = _deduplicate_log_rows(log_rows)
    metrics_7d = _window_metrics(rows, planned_workouts, start_7d, window_end)
    metrics_28d = _window_metrics(rows, planned_workouts, start_28d, window_end)

    availability = {
        "training_logs": metrics_28d.sessions > 0,
        "actual_distance_km": metrics_28d.distance_coverage > 0,
        "actual_duration_seconds": metrics_28d.duration_coverage > 0,
        "rpe": metrics_28d.rpe_coverage > 0,
        "heart_rate": metrics_28d.heart_rate_coverage > 0,
        "planned_workouts": metrics_28d.planned_sessions > 0,
        "goal_context": cycle is not None,
        "intensity_classification": metrics_28d.distance_km is not None and metrics_28d.unclassified_distance_count == 0,
    }
    if metrics_28d.completed_sessions:
        completeness_parts = [
            metrics_28d.valid_workout_count / metrics_28d.completed_sessions,
            metrics_28d.distance_coverage,
            metrics_28d.duration_coverage,
            metrics_28d.rpe_coverage,
            metrics_28d.heart_rate_coverage,
            1.0 if metrics_28d.planned_sessions else 0.0,
        ]
        confidence = round(sum(completeness_parts) / len(completeness_parts), 4)
    else:
        confidence = 0.0

    limitations: set[str] = {"intensity_distance_uses_main_workout_type"}
    if metrics_28d.completed_sessions == 0:
        limitations.add("no_completed_workouts_28d")
    for days, metrics in ((7, metrics_7d), (28, metrics_28d)):
        if metrics.planned_sessions == 0:
            limitations.add(f"completion_rate_{days}d_unavailable_no_planned_sessions")
        if metrics.completed_sessions and metrics.rpe_coverage < 1:
            limitations.add(f"rpe_incomplete_{days}d")
        if metrics.completed_sessions and metrics.heart_rate_coverage < 1:
            limitations.add(f"heart_rate_incomplete_{days}d")
    if metrics_28d.invalid_rpe_count:
        limitations.add(f"invalid_rpe_excluded:{metrics_28d.invalid_rpe_count}")
    if metrics_28d.invalid_distance_count:
        limitations.add(f"negative_distance_excluded:{metrics_28d.invalid_distance_count}")
    if metrics_28d.invalid_duration_count:
        limitations.add(f"negative_duration_excluded:{metrics_28d.invalid_duration_count}")
    if metrics_28d.composite_type_count:
        limitations.add("composite_workout_intensity_segments_not_split")
    if metrics_28d.unclassified_distance_count:
        limitations.add("unclassified_workout_distance_excluded_from_intensity_buckets")
    if last_quality_date is None:
        limitations.add("days_since_last_quality_session_unavailable")

    days_since_quality = None
    if last_quality_date is not None and last_quality_date <= window_end:
        days_since_quality = (window_end - last_quality_date).days

    return RunnerStateSnapshot(
        identity=RunnerIdentityReference(
            runner_id=runner_id,
            generated_at=generated_at,
            timezone=timezone_name,
            calculation_window_end=window_end,
            calculation_window_start_7d=start_7d,
            calculation_window_start_28d=start_28d,
        ),
        goal_context=_goal_context(cycle, window_end),
        recent_training=RecentTrainingMetrics(
            distance_7d_km=metrics_7d.distance_km,
            distance_28d_km=metrics_28d.distance_km,
            duration_7d_minutes=metrics_7d.duration_minutes,
            duration_28d_minutes=metrics_28d.duration_minutes,
            sessions_7d=metrics_7d.sessions,
            sessions_28d=metrics_28d.sessions,
            completed_sessions_7d=metrics_7d.completed_sessions,
            completed_sessions_28d=metrics_28d.completed_sessions,
            planned_sessions_7d=metrics_7d.planned_sessions,
            planned_sessions_28d=metrics_28d.planned_sessions,
            completion_rate_7d=_completion_rate(metrics_7d),
            completion_rate_28d=_completion_rate(metrics_28d),
            average_rpe_7d=metrics_7d.average_rpe,
            average_rpe_28d=metrics_28d.average_rpe,
        ),
        intensity=IntensityMetrics(
            easy_distance_7d_km=metrics_7d.easy_distance_km,
            moderate_distance_7d_km=metrics_7d.moderate_distance_km,
            hard_distance_7d_km=metrics_7d.hard_distance_km,
            easy_distance_28d_km=metrics_28d.easy_distance_km,
            moderate_distance_28d_km=metrics_28d.moderate_distance_km,
            hard_distance_28d_km=metrics_28d.hard_distance_km,
            hard_distance_ratio_7d=metrics_7d.hard_distance_ratio,
            hard_distance_ratio_28d=metrics_28d.hard_distance_ratio,
            quality_sessions_7d=metrics_7d.quality_sessions,
            quality_sessions_28d=metrics_28d.quality_sessions,
            long_run_distance_7d_km=metrics_7d.long_run_distance_km,
            long_run_distance_28d_km=metrics_28d.long_run_distance_km,
            days_since_last_quality_session=days_since_quality,
        ),
        inferred_state=InferredStatePlaceholders(),
        data_quality=RunnerStateDataQuality(
            data_quality_level=_quality_level(confidence, metrics_28d.completed_sessions),
            confidence=confidence,
            available_fields=[field for field in DATA_FIELDS if availability[field]],
            missing_fields=[field for field in DATA_FIELDS if not availability[field]],
            valid_workout_count_7d=metrics_7d.valid_workout_count,
            valid_workout_count_28d=metrics_28d.valid_workout_count,
            rpe_coverage_7d=metrics_7d.rpe_coverage,
            rpe_coverage_28d=metrics_28d.rpe_coverage,
            heart_rate_coverage_7d=metrics_7d.heart_rate_coverage,
            heart_rate_coverage_28d=metrics_28d.heart_rate_coverage,
            limitations=sorted(limitations),
        ),
    )


class RunnerStateService:
    def __init__(self, db: Session, timezone_name: str = APP_TIMEZONE.key) -> None:
        self.db = db
        self.timezone_name = timezone_name

    def get_current(self, current_user: UserAccount, *, generated_at: datetime | None = None) -> RunnerStateSnapshot:
        zone = ZoneInfo(self.timezone_name)
        generated = generated_at or datetime.now(zone)
        window_end = generated.astimezone(zone).date() if generated.tzinfo else generated.date()
        start_28d = window_end - timedelta(days=WINDOW_28D_DAYS - 1)
        cycle = training_cycle_lifecycle_service.get_active_cycle(self.db, current_user.id)
        log_rows = _query_logs(self.db, current_user.id, start_28d, window_end)
        planned = list(
            self.db.scalars(
                select(PlannedWorkout)
                .where(
                    PlannedWorkout.user_id == current_user.id,
                    PlannedWorkout.workout_date >= start_28d,
                    PlannedWorkout.workout_date <= window_end,
                    PlannedWorkout.lifecycle_status == PlannedWorkoutLifecycleStatus.planned,
                )
                .order_by(PlannedWorkout.workout_date, PlannedWorkout.session_index, PlannedWorkout.id)
            )
        )
        last_quality_date = self.db.scalar(
            select(func.max(func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date)))
            .select_from(WorkoutLog)
            .outerjoin(PlannedWorkout, PlannedWorkout.id == WorkoutLog.planned_workout_id)
            .where(
                WorkoutLog.user_id == current_user.id,
                WorkoutLog.status_normalized.in_(COMPLETED_STATUSES),
                func.coalesce(PlannedWorkout.workout_date, WorkoutLog.activity_date) <= window_end,
                or_(
                    PlannedWorkout.main_type_normalized.in_([WorkoutMainTypeNormalized(item) for item in KEY_WORKOUT_TYPES]),
                    and_(PlannedWorkout.id.is_(None), WorkoutLog.workout_type.in_(KEY_WORKOUT_TYPES)),
                ),
            )
        )
        snapshot = build_runner_state_snapshot(
            runner_id=current_user.id,
            cycle=cycle,
            log_rows=log_rows,
            planned_workouts=planned,
            generated_at=generated,
            timezone_name=self.timezone_name,
            calculation_window_end=window_end,
            last_quality_date=last_quality_date,
        )
        logger.info(
            "runner_state_snapshot_generated runner_id=%s window_end=%s valid_workouts_28d=%s data_quality=%s",
            current_user.id,
            window_end,
            snapshot.data_quality.valid_workout_count_28d,
            snapshot.data_quality.data_quality_level.value,
        )
        return snapshot
