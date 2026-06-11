from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import PlannedWorkout
from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.common.exceptions import BadRequestError
from server.schemas.training_calendar import (
    TrainingCalendarDayRead,
    TrainingCalendarRead,
    TrainingCalendarSummaryRead,
)

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def get_training_calendar(
    db: Session,
    user_id: int,
    *,
    cycle_id: int | None = None,
    month: str,
) -> TrainingCalendarRead:
    start_date, end_date = month_bounds(month)
    stmt = (
        select(PlannedWorkout)
        .options(selectinload(PlannedWorkout.workout_log))
        .where(
            PlannedWorkout.user_id == user_id,
            PlannedWorkout.workout_date >= start_date,
            PlannedWorkout.workout_date <= end_date,
        )
    )
    if cycle_id is not None:
        stmt = stmt.where(PlannedWorkout.cycle_id == cycle_id)
    stmt = stmt.order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order, PlannedWorkout.id)
    workouts = list(db.scalars(stmt))

    workout_by_day = {workout.workout_date: workout for workout in workouts if workout.workout_date is not None}
    days: list[TrainingCalendarDayRead] = []
    for day_number in range(1, end_date.day + 1):
        current_date = date(start_date.year, start_date.month, day_number)
        workout = workout_by_day.get(current_date)
        days.append(build_day(current_date, workout))

    summary = build_summary(days)
    return TrainingCalendarRead(month=month, days=days, summary=summary)


def month_bounds(month: str) -> tuple[date, date]:
    try:
        year_text, month_text = month.split("-", 1)
        year = int(year_text)
        month_number = int(month_text)
        if len(year_text) != 4 or len(month_text) != 2:
            raise ValueError
        last_day = calendar.monthrange(year, month_number)[1]
    except ValueError as exc:
        raise BadRequestError("Month must use YYYY-MM format.") from exc
    return date(year, month_number, 1), date(year, month_number, last_day)


def build_day(current_date: date, workout: PlannedWorkout | None) -> TrainingCalendarDayRead:
    if workout is None:
        return TrainingCalendarDayRead(
            date=current_date,
            weekday=WEEKDAY_LABELS[current_date.weekday()],
            status_normalized=WorkoutStatusNormalized.rest,
        )

    log = workout.workout_log
    status = log.status_normalized if log else WorkoutStatusNormalized.not_started
    if workout.main_type_normalized == WorkoutMainTypeNormalized.rest and status == WorkoutStatusNormalized.not_started:
        status = WorkoutStatusNormalized.rest

    planned_distance = workout.planned_distance_km
    actual_distance = log.actual_distance_km if log else None
    completion_rate = log.completion_rate if log else None
    if completion_rate is None and planned_distance and actual_distance is not None and planned_distance > 0:
        completion_rate = (Decimal(actual_distance) / Decimal(planned_distance)).quantize(Decimal("0.01"))

    return TrainingCalendarDayRead(
        date=current_date,
        weekday=workout.weekday or WEEKDAY_LABELS[current_date.weekday()],
        planned_workout_id=workout.id,
        planned_content=workout.planned_content,
        planned_distance_km=planned_distance,
        main_type=workout.main_type_normalized,
        status_normalized=status,
        actual_distance_km=actual_distance,
        avg_pace_seconds_per_km=log.avg_pace_seconds_per_km if log else None,
        avg_heart_rate=log.avg_heart_rate if log else None,
        rpe=log.rpe if log else None,
        review_note=log.review_note if log else None,
        completion_rate=completion_rate,
    )


def build_summary(days: list[TrainingCalendarDayRead]) -> TrainingCalendarSummaryRead:
    planned_total = sum((day.planned_distance_km or Decimal("0")) for day in days)
    actual_total = sum((day.actual_distance_km or Decimal("0")) for day in days)
    completed_days = sum(1 for day in days if day.status_normalized.value.startswith("completed"))
    missed_days = sum(
        1
        for day in days
        if day.status_normalized in {WorkoutStatusNormalized.missed, WorkoutStatusNormalized.skipped}
    )
    completion_rate = Decimal("0")
    if planned_total > 0:
        completion_rate = (actual_total / planned_total).quantize(Decimal("0.01"))

    return TrainingCalendarSummaryRead(
        planned_distance_km=planned_total,
        actual_distance_km=actual_total,
        completion_rate=completion_rate,
        completed_days=completed_days,
        missed_days=missed_days,
    )
