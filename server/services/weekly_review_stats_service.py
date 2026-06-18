from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import BlockReview, PlannedWorkout, TrainingBlock, WorkoutLog
from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.domain.review_thresholds import HIGH_INTENSITY_TYPES, KEY_WORKOUT_TYPES
from server.common.exceptions import BadRequestError
from server.schemas.weekly_review import WeeklyReviewMetrics
from server.services.training_block_service import get_training_block
from server.services.training_cycle_service import get_training_cycle

APP_TIMEZONE = ZoneInfo("Asia/Shanghai")
COMPLETED_STATUSES = {
    WorkoutStatusNormalized.completed_high,
    WorkoutStatusNormalized.completed_normal,
    WorkoutStatusNormalized.completed_adjusted,
}
REST_STATUSES = {WorkoutStatusNormalized.rest, WorkoutStatusNormalized.rest_or_cancelled}


def local_today() -> date:
    return datetime.now(APP_TIMEZONE).date()


def _number(value: Decimal | int | float | None) -> float:
    return round(float(value or 0), 4)


def _average(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def _week_bounds(block: TrainingBlock, workouts: list[PlannedWorkout]) -> tuple[date, date]:
    dated = [item.workout_date for item in workouts if item.workout_date]
    start = block.start_date or (min(dated) if dated else None)
    end = block.end_date or (max(dated) if dated else None)
    if start is None or end is None:
        raise BadRequestError("Training block must have a date range or dated workouts.")
    return start, end


def _daily_item(workout: PlannedWorkout, today: date) -> dict:
    log = workout.workout_log
    status = log.status_normalized if log else WorkoutStatusNormalized.not_started
    effective_status = status
    if (
        status == WorkoutStatusNormalized.not_started
        and workout.workout_date
        and workout.workout_date < today
        and workout.main_type_normalized != WorkoutMainTypeNormalized.rest
    ):
        effective_status = WorkoutStatusNormalized.missed
    return {
        "planned_workout_id": workout.id,
        "date": workout.workout_date.isoformat() if workout.workout_date else None,
        "planned_content": workout.planned_content,
        "planned_distance_km": _number(workout.planned_distance_km),
        "actual_distance_km": _number(log.actual_distance_km if log else None),
        "main_type": workout.main_type_normalized.value,
        "status": effective_status.value,
        "rpe": log.rpe if log else None,
        "pain_level": log.pain_level if log else None,
        "target_pace_text": workout.target_pace_text,
    }


def build_weekly_review_metrics(
    db: Session,
    current_user_id: int,
    cycle_id: int,
    source_block_id: int,
) -> WeeklyReviewMetrics:
    cycle = get_training_cycle(db, cycle_id, current_user_id)
    block = get_training_block(db, source_block_id, current_user_id)
    if block.cycle_id != cycle.id:
        raise BadRequestError("Source block does not belong to the selected cycle.")

    workouts = list(
        db.scalars(
            select(PlannedWorkout)
            .options(selectinload(PlannedWorkout.workout_log))
            .where(
                PlannedWorkout.user_id == current_user_id,
                PlannedWorkout.cycle_id == cycle_id,
                PlannedWorkout.block_id == source_block_id,
            )
            .order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order, PlannedWorkout.id)
        )
    )
    week_start, week_end = _week_bounds(block, workouts)
    workouts = [
        item
        for item in workouts
        if item.workout_date is None or week_start <= item.workout_date <= week_end
    ]
    today = local_today()

    planned_distance = sum((_number(item.planned_distance_km) for item in workouts), 0.0)
    eligible_logged_workouts = [
        item for item in workouts if item.workout_log and (item.workout_date is None or item.workout_date <= today)
    ]
    actual_distance = sum((_number(item.workout_log.actual_distance_km) for item in eligible_logged_workouts), 0.0)
    non_rest = [item for item in workouts if item.main_type_normalized != WorkoutMainTypeNormalized.rest]
    logs = [
        item.workout_log
        for item in non_rest
        if item.workout_log and (item.workout_date is None or item.workout_date <= today)
    ]
    valid_logs = [log for log in logs if log.status_normalized != WorkoutStatusNormalized.not_started]
    completed = [log for log in logs if log.status_normalized in COMPLETED_STATUSES]

    counts = defaultdict(int)
    for item in workouts:
        status = item.workout_log.status_normalized if item.workout_log else WorkoutStatusNormalized.not_started
        if item.workout_date and item.workout_date > today:
            continue
        if item.main_type_normalized == WorkoutMainTypeNormalized.rest or status in REST_STATUSES:
            counts["rest"] += 1
        elif status == WorkoutStatusNormalized.completed_high:
            counts["completed_high"] += 1
        elif status == WorkoutStatusNormalized.completed_normal:
            counts["completed_normal"] += 1
        elif status == WorkoutStatusNormalized.completed_adjusted:
            counts["completed_adjusted"] += 1
        elif status == WorkoutStatusNormalized.skipped:
            counts["skipped"] += 1
        elif status == WorkoutStatusNormalized.missed or (
            status == WorkoutStatusNormalized.not_started and item.workout_date and item.workout_date < today
        ):
            counts["missed"] += 1

    planned_by_type: dict[str, float] = defaultdict(float)
    actual_by_type: dict[str, float] = defaultdict(float)
    for item in workouts:
        key = item.main_type_normalized.value
        planned_by_type[key] += _number(item.planned_distance_km)
        if item.workout_log and (item.workout_date is None or item.workout_date <= today):
            actual_by_type[key] += _number(item.workout_log.actual_distance_km)

    rpes = [float(log.rpe) for log in completed if log.rpe is not None]
    key_logs = [
        item.workout_log
        for item in workouts
        if item.main_type_normalized.value in KEY_WORKOUT_TYPES
        and item.workout_log
        and (item.workout_date is None or item.workout_date <= today)
        and item.workout_log.status_normalized in COMPLETED_STATUSES
    ]
    key_rpes = [float(log.rpe) for log in key_logs if log.rpe is not None]
    pain_levels = [log.pain_level for log in valid_logs if log.pain_level is not None]
    sleep_values = [float(log.sleep_hours) for log in valid_logs if log.sleep_hours is not None]
    hrv_values = [float(log.hrv) for log in valid_logs if log.hrv is not None]
    morning_values = [float(log.morning_heart_rate) for log in valid_logs if log.morning_heart_rate is not None]

    key_workouts = [
        _daily_item(item, today)
        for item in workouts
        if item.main_type_normalized.value in KEY_WORKOUT_TYPES
    ]
    long_runs = [item for item in workouts if item.main_type_normalized == WorkoutMainTypeNormalized.long_run]
    long_run = _daily_item(long_runs[-1], today) if long_runs else None

    recent_end = min(week_end, today)
    recent_start = recent_end - timedelta(days=27)
    recent_logs = list(
        db.scalars(
            select(WorkoutLog)
            .join(PlannedWorkout, PlannedWorkout.id == WorkoutLog.planned_workout_id)
            .where(
                WorkoutLog.user_id == current_user_id,
                PlannedWorkout.workout_date >= recent_start,
                PlannedWorkout.workout_date <= recent_end,
            )
        )
    )
    recent_28_distance = sum((_number(log.actual_distance_km) for log in recent_logs), 0.0)
    seven_start = recent_end - timedelta(days=6)
    recent_7_distance = sum(
        _number(log.actual_distance_km)
        for log in recent_logs
        if log.planned_workout and log.planned_workout.workout_date >= seven_start
    )
    weekly_avg_28 = recent_28_distance / 4
    load_change = round((recent_7_distance / weekly_avg_28 - 1) * 100, 1) if weekly_avg_28 > 0 else None

    intense_dates = sorted(
        {
            item.workout_date
            for item in workouts
            if item.workout_date
            and item.main_type_normalized.value in HIGH_INTENSITY_TYPES
            and item.workout_log
            and item.workout_log.status_normalized in COMPLETED_STATUSES
        }
    )
    consecutive = [
        [left.isoformat(), right.isoformat()]
        for left, right in zip(intense_dates, intense_dates[1:])
        if right - left == timedelta(days=1)
    ]

    missing_fields = [
        field
        for field, values in (
            ("sleep_hours", sleep_values),
            ("hrv", hrv_values),
            ("morning_heart_rate", morning_values),
            ("average_heart_rate", [log.avg_heart_rate for log in valid_logs if log.avg_heart_rate is not None]),
            ("weight_kg", [log.weight_kg for log in valid_logs if log.weight_kg is not None]),
            ("leg_feeling", [log.leg_feeling for log in valid_logs if log.leg_feeling]),
            ("pain_information", pain_levels),
        )
        if not values
    ]

    return WeeklyReviewMetrics(
        week_start_date=week_start,
        week_end_date=week_end,
        is_week_complete=week_end < today,
        planned_distance_km=round(planned_distance, 2),
        actual_distance_km=round(actual_distance, 2),
        completion_rate=round(actual_distance / planned_distance, 4) if planned_distance > 0 else 0,
        planned_workout_days=len(non_rest),
        completed_workout_days=len(completed),
        completed_high_count=counts["completed_high"],
        completed_normal_count=counts["completed_normal"],
        completed_adjusted_count=counts["completed_adjusted"],
        missed_count=counts["missed"],
        rest_count=counts["rest"],
        skipped_count=counts["skipped"],
        avg_rpe=_average(rpes),
        key_workout_avg_rpe=_average(key_rpes),
        max_pain_level=max(pain_levels) if pain_levels else None,
        planned_type_distance={key: round(value, 2) for key, value in planned_by_type.items()},
        actual_type_distance={key: round(value, 2) for key, value in actual_by_type.items()},
        key_workouts=key_workouts,
        long_run=long_run,
        recent_7d_distance_km=round(recent_7_distance, 2),
        recent_28d_weekly_avg_km=round(weekly_avg_28, 2),
        load_change_percentage=load_change,
        consecutive_high_intensity_days=consecutive,
        logged_workout_ratio=round(len(valid_logs) / len(non_rest), 4) if non_rest else 0,
        valid_log_count=len(valid_logs),
        avg_sleep_hours=_average(sleep_values),
        avg_hrv=_average(hrv_values),
        avg_morning_heart_rate=_average(morning_values),
        missing_fields=missing_fields,
        daily_workouts=[_daily_item(item, today) for item in workouts],
    )


def save_block_review_metrics(
    db: Session, current_user_id: int, source_block_id: int, metrics: WeeklyReviewMetrics
) -> BlockReview:
    review = db.scalar(
        select(BlockReview).where(BlockReview.block_id == source_block_id, BlockReview.user_id == current_user_id)
    )
    if review is None:
        review = BlockReview(block_id=source_block_id, user_id=current_user_id)
        db.add(review)
    review.planned_distance_km = Decimal(str(metrics.planned_distance_km))
    review.actual_distance_km = Decimal(str(metrics.actual_distance_km))
    review.completion_rate = Decimal(str(metrics.completion_rate))
    review.avg_rpe = Decimal(str(metrics.avg_rpe)) if metrics.avg_rpe is not None else None
    review.max_pain_level = metrics.max_pain_level
    return review
