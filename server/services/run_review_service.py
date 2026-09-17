from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import ExternalActivity, PlannedWorkout, WorkoutLog
from server.common.exceptions import NotFoundError
from server.schemas.run_review import RunReviewActualRead, RunReviewPlanRead, RunReviewRead


def get_run_review(db: Session, *, user_id: int, activity_id: int) -> RunReviewRead:
    """Build a read-only plan-versus-actual review for one owned activity."""
    activity = db.scalar(
        select(ExternalActivity).where(
            ExternalActivity.id == activity_id,
            ExternalActivity.user_id == user_id,
        )
    )
    if activity is None:
        raise NotFoundError("Activity not found.")
    plan = None
    if activity.planned_workout_id is not None:
        plan = db.scalar(
            select(PlannedWorkout).where(
                PlannedWorkout.id == activity.planned_workout_id,
                PlannedWorkout.user_id == user_id,
            )
        )
    log = None
    if activity.workout_log_id is not None:
        log = db.scalar(
            select(WorkoutLog).where(WorkoutLog.id == activity.workout_log_id, WorkoutLog.user_id == user_id)
        )
    planned_distance = plan.planned_distance_km if plan is not None else None
    actual_distance = activity.distance_m / Decimal("1000") if activity.distance_m is not None else None
    distance_delta = actual_distance - planned_distance if actual_distance is not None and planned_distance is not None else None
    distance_delta_percent = None
    if distance_delta is not None and planned_distance and planned_distance > 0:
        distance_delta_percent = (distance_delta / planned_distance * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    limitations: list[str] = []
    if plan is None:
        limitations.append("planned_workout_unavailable")
    if actual_distance is None:
        limitations.append("actual_distance_unavailable")
    if log is None or log.rpe is None:
        limitations.append("rpe_unavailable")
    return RunReviewRead(
        activity_id=activity.id,
        plan=RunReviewPlanRead(
            planned_workout_id=plan.id if plan else None,
            date=plan.workout_date if plan else None,
            content=plan.planned_content if plan else None,
            distance_km=planned_distance,
            workout_type=plan.main_type_normalized.value if plan and plan.main_type_normalized else None,
        ),
        actual=RunReviewActualRead(
            activity_id=activity.id,
            provider=activity.provider,
            date=activity.activity_date,
            activity_type=activity.activity_type,
            distance_km=actual_distance,
            duration_seconds=activity.duration_seconds,
            average_pace_seconds_per_km=activity.average_pace_seconds_per_km,
            average_heart_rate_bpm=activity.average_heart_rate_bpm,
            rpe=log.rpe if log else None,
        ),
        distance_delta_km=distance_delta,
        distance_delta_percent=distance_delta_percent,
        data_quality=activity.data_quality,
        limitations=limitations,
    )
