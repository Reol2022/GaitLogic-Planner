from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import PlannedWorkout, WorkoutLog
from planner_core.enums import PlannedWorkoutLifecycleStatus, WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.planned_workout import PlannedWorkoutCreate, PlannedWorkoutUpdate
from server.services.training_block_service import get_training_block
from server.services.training_cycle_service import get_training_cycle
from server.services.training_cycle_lifecycle_service import get_active_cycle


def list_planned_workouts(
    db: Session,
    user_id: int,
    cycle_id: int | None = None,
    block_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    main_type_normalized: WorkoutMainTypeNormalized | None = None,
) -> list[PlannedWorkout]:
    if cycle_id is None:
        active_cycle = get_active_cycle(db, user_id)
        if active_cycle is None:
            return []
        cycle_id = active_cycle.id
    stmt = (
        select(PlannedWorkout)
        .options(selectinload(PlannedWorkout.workout_log))
        .where(
            PlannedWorkout.user_id == user_id,
            PlannedWorkout.lifecycle_status == PlannedWorkoutLifecycleStatus.planned,
        )
    )
    if cycle_id is not None:
        stmt = stmt.where(PlannedWorkout.cycle_id == cycle_id)
    if block_id is not None:
        stmt = stmt.where(PlannedWorkout.block_id == block_id)
    if start_date is not None:
        stmt = stmt.where(PlannedWorkout.workout_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(PlannedWorkout.workout_date <= end_date)
    if main_type_normalized is not None:
        stmt = stmt.where(PlannedWorkout.main_type_normalized == main_type_normalized)
    stmt = stmt.order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order, PlannedWorkout.id)
    return list(db.scalars(stmt))


def get_planned_workout(db: Session, workout_id: int, user_id: int) -> PlannedWorkout:
    stmt = (
        select(PlannedWorkout)
        .options(selectinload(PlannedWorkout.workout_log))
        .where(PlannedWorkout.id == workout_id, PlannedWorkout.user_id == user_id)
    )
    workout = db.scalar(stmt)
    if workout is None:
        raise NotFoundError("Planned workout not found.")
    return workout


def create_planned_workout(
    db: Session,
    payload: PlannedWorkoutCreate,
    user_id: int,
) -> PlannedWorkout:
    get_training_cycle(db, payload.cycle_id, user_id)
    block = get_training_block(db, payload.block_id, user_id)
    if block.cycle_id != payload.cycle_id:
        raise BadRequestError("Training block does not belong to the selected cycle.")
    workout = PlannedWorkout(
        **payload.model_dump(),
        user_id=user_id,
        workout_log=WorkoutLog(
            user_id=user_id,
            cycle_id=payload.cycle_id,
            status_raw=None,
            status_normalized=WorkoutStatusNormalized.not_started,
        ),
    )
    db.add(workout)
    db.commit()
    db.refresh(workout)
    return get_planned_workout(db, workout.id, user_id)


def update_planned_workout(
    db: Session,
    workout_id: int,
    payload: PlannedWorkoutUpdate,
    user_id: int,
) -> PlannedWorkout:
    workout = get_planned_workout(db, workout_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    next_cycle_id = data.get("cycle_id", workout.cycle_id)
    next_block_id = data.get("block_id", workout.block_id)
    if "cycle_id" in data:
        get_training_cycle(db, next_cycle_id, user_id)
    if "block_id" in data or "cycle_id" in data:
        block = get_training_block(db, next_block_id, user_id)
        if block.cycle_id != next_cycle_id:
            raise BadRequestError("Training block does not belong to the selected cycle.")
    for key, value in data.items():
        setattr(workout, key, value)
    db.commit()
    db.refresh(workout)
    return get_planned_workout(db, workout.id, user_id)


def delete_planned_workout(db: Session, workout_id: int, user_id: int) -> None:
    workout = get_planned_workout(db, workout_id, user_id)
    db.delete(workout)
    db.commit()


def get_today_workouts(db: Session, workout_date: date, user_id: int) -> list[PlannedWorkout]:
    return list_planned_workouts(db, user_id, start_date=workout_date, end_date=workout_date)
