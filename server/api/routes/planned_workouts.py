from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from planner_core.enums import WorkoutMainTypeNormalized
from server.api.deps import get_db
from server.common.response import MessageResponse
from server.schemas.planned_workout import (
    PlannedWorkoutCreate,
    PlannedWorkoutRead,
    PlannedWorkoutUpdate,
    PlannedWorkoutWithLogRead,
)
from server.services import planned_workout_service

router = APIRouter(tags=["planned workouts"])


@router.get("/planned-workouts", response_model=list[PlannedWorkoutWithLogRead])
def list_planned_workouts(
    cycle_id: int | None = Query(default=None),
    block_id: int | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    main_type_normalized: WorkoutMainTypeNormalized | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return planned_workout_service.list_planned_workouts(
        db,
        cycle_id=cycle_id,
        block_id=block_id,
        start_date=start_date,
        end_date=end_date,
        main_type_normalized=main_type_normalized,
    )


@router.post(
    "/planned-workouts",
    response_model=PlannedWorkoutWithLogRead,
    status_code=status.HTTP_201_CREATED,
)
def create_planned_workout(payload: PlannedWorkoutCreate, db: Session = Depends(get_db)):
    return planned_workout_service.create_planned_workout(db, payload)


@router.get("/planned-workouts/{workout_id}", response_model=PlannedWorkoutWithLogRead)
def get_planned_workout(workout_id: int, db: Session = Depends(get_db)):
    return planned_workout_service.get_planned_workout(db, workout_id)


@router.put("/planned-workouts/{workout_id}", response_model=PlannedWorkoutWithLogRead)
def update_planned_workout(
    workout_id: int,
    payload: PlannedWorkoutUpdate,
    db: Session = Depends(get_db),
):
    return planned_workout_service.update_planned_workout(db, workout_id, payload)


@router.delete("/planned-workouts/{workout_id}", response_model=MessageResponse)
def delete_planned_workout(workout_id: int, db: Session = Depends(get_db)):
    planned_workout_service.delete_planned_workout(db, workout_id)
    return MessageResponse(message="Planned workout deleted.")


@router.get("/today", response_model=list[PlannedWorkoutWithLogRead])
def get_today(
    date: date = Query(...),
    db: Session = Depends(get_db),
):
    return planned_workout_service.get_today_workouts(db, date)

