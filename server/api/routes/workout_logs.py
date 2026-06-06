from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.workout_log import WorkoutLogRead, WorkoutLogUpdate
from server.services import workout_log_service

router = APIRouter(prefix="/workout-logs", tags=["workout logs"])


@router.get("/{planned_workout_id}", response_model=WorkoutLogRead)
def get_workout_log(
    planned_workout_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return workout_log_service.get_workout_log_by_planned_workout(
        db,
        planned_workout_id,
        current_user.id,
    )


@router.put("/{planned_workout_id}", response_model=WorkoutLogRead)
def update_workout_log(
    planned_workout_id: int,
    payload: WorkoutLogUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return workout_log_service.update_workout_log(
        db,
        planned_workout_id,
        payload,
        current_user.id,
    )
