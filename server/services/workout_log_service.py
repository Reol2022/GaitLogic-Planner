from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import WorkoutLog
from server.common.exceptions import NotFoundError
from server.schemas.workout_log import WorkoutLogUpdate
from server.services.planned_workout_service import get_planned_workout


def get_workout_log_by_planned_workout(
    db: Session,
    planned_workout_id: int,
    user_id: int,
) -> WorkoutLog:
    get_planned_workout(db, planned_workout_id, user_id)
    log = db.scalar(
        select(WorkoutLog).where(
            WorkoutLog.planned_workout_id == planned_workout_id,
            WorkoutLog.user_id == user_id,
        )
    )
    if log is None:
        raise NotFoundError("Workout log not found.")
    return log


def update_workout_log(
    db: Session,
    planned_workout_id: int,
    payload: WorkoutLogUpdate,
    user_id: int,
) -> WorkoutLog:
    log = get_workout_log_by_planned_workout(db, planned_workout_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    actual_distance = data.get("actual_distance_km", log.actual_distance_km)
    actual_duration = data.get("actual_duration_seconds", log.actual_duration_seconds)
    should_auto_calculate_pace = (
        "avg_pace_seconds_per_km" not in data or data.get("avg_pace_seconds_per_km") in (None, 0)
    )
    if (
        should_auto_calculate_pace
        and actual_distance is not None
        and actual_duration is not None
        and actual_distance > 0
    ):
        data["avg_pace_seconds_per_km"] = int(round(actual_duration / float(actual_distance)))
    for key, value in data.items():
        setattr(log, key, value)
    db.commit()
    db.refresh(log)
    return log
