from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import TrainingCycle
from server.common.exceptions import NotFoundError
from server.schemas.training_cycle import TrainingCycleCreate, TrainingCycleUpdate


def list_training_cycles(db: Session, user_id: int) -> list[TrainingCycle]:
    return list(
        db.scalars(
            select(TrainingCycle)
            .where(TrainingCycle.user_id == user_id)
            .order_by(TrainingCycle.start_date, TrainingCycle.id)
        )
    )


def get_training_cycle(db: Session, cycle_id: int, user_id: int) -> TrainingCycle:
    cycle = db.scalar(
        select(TrainingCycle).where(
            TrainingCycle.id == cycle_id,
            TrainingCycle.user_id == user_id,
        )
    )
    if cycle is None:
        raise NotFoundError("Training cycle not found.")
    return cycle


def create_training_cycle(db: Session, payload: TrainingCycleCreate, user_id: int) -> TrainingCycle:
    cycle = TrainingCycle(**payload.model_dump(), user_id=user_id)
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def update_training_cycle(
    db: Session,
    cycle_id: int,
    payload: TrainingCycleUpdate,
    user_id: int,
) -> TrainingCycle:
    cycle = get_training_cycle(db, cycle_id, user_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cycle, key, value)
    db.commit()
    db.refresh(cycle)
    return cycle


def delete_training_cycle(db: Session, cycle_id: int, user_id: int) -> None:
    cycle = get_training_cycle(db, cycle_id, user_id)
    db.delete(cycle)
    db.commit()
