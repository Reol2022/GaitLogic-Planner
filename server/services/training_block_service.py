from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import TrainingBlock
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.training_block import TrainingBlockCreate, TrainingBlockUpdate
from server.services.training_cycle_service import get_training_cycle


def list_training_blocks(db: Session, cycle_id: int | None = None) -> list[TrainingBlock]:
    stmt = select(TrainingBlock)
    if cycle_id is not None:
        stmt = stmt.where(TrainingBlock.cycle_id == cycle_id)
    stmt = stmt.order_by(TrainingBlock.cycle_id, TrainingBlock.sort_order)
    return list(db.scalars(stmt))


def get_training_block(db: Session, block_id: int) -> TrainingBlock:
    block = db.get(TrainingBlock, block_id)
    if block is None:
        raise NotFoundError("Training block not found.")
    return block


def create_training_block(db: Session, payload: TrainingBlockCreate) -> TrainingBlock:
    get_training_cycle(db, payload.cycle_id)
    block = TrainingBlock(**payload.model_dump())
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def update_training_block(
    db: Session,
    block_id: int,
    payload: TrainingBlockUpdate,
) -> TrainingBlock:
    block = get_training_block(db, block_id)
    data = payload.model_dump(exclude_unset=True)
    if "cycle_id" in data:
        get_training_cycle(db, data["cycle_id"])
    if "target_distance_min_km" in data and "target_distance_max_km" in data:
        min_km = data["target_distance_min_km"]
        max_km = data["target_distance_max_km"]
        if min_km is not None and max_km is not None and min_km > max_km:
            raise BadRequestError("Minimum target distance cannot exceed maximum distance.")
    for key, value in data.items():
        setattr(block, key, value)
    db.commit()
    db.refresh(block)
    return block


def delete_training_block(db: Session, block_id: int) -> None:
    block = get_training_block(db, block_id)
    db.delete(block)
    db.commit()

