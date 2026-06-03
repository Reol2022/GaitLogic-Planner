from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import WorkoutLog
from server.common.exceptions import NotFoundError
from server.schemas.workout_log import WorkoutLogUpdate
from server.services.planned_workout_service import get_planned_workout


def get_workout_log_by_planned_workout(
    db: Session,
    planned_workout_id: int,
) -> WorkoutLog:
    get_planned_workout(db, planned_workout_id)
    log = db.scalar(
        select(WorkoutLog).where(WorkoutLog.planned_workout_id == planned_workout_id)
    )
    if log is None:
        raise NotFoundError("Workout log not found.")
    return log


def update_workout_log(
    db: Session,
    planned_workout_id: int,
    payload: WorkoutLogUpdate,
) -> WorkoutLog:
    log = get_workout_log_by_planned_workout(db, planned_workout_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, key, value)
    db.commit()
    db.refresh(log)
    return log

