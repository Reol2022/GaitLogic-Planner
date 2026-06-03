from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import TrainingCycle
from server.common.exceptions import NotFoundError
from server.schemas.training_cycle import TrainingCycleCreate, TrainingCycleUpdate


def list_training_cycles(db: Session) -> list[TrainingCycle]:
    return list(db.scalars(select(TrainingCycle).order_by(TrainingCycle.start_date, TrainingCycle.id)))


def get_training_cycle(db: Session, cycle_id: int) -> TrainingCycle:
    cycle = db.get(TrainingCycle, cycle_id)
    if cycle is None:
        raise NotFoundError("Training cycle not found.")
    return cycle


def create_training_cycle(db: Session, payload: TrainingCycleCreate) -> TrainingCycle:
    cycle = TrainingCycle(**payload.model_dump())
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def update_training_cycle(
    db: Session,
    cycle_id: int,
    payload: TrainingCycleUpdate,
) -> TrainingCycle:
    cycle = get_training_cycle(db, cycle_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cycle, key, value)
    db.commit()
    db.refresh(cycle)
    return cycle


def delete_training_cycle(db: Session, cycle_id: int) -> None:
    cycle = get_training_cycle(db, cycle_id)
    db.delete(cycle)
    db.commit()

