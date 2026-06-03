from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from server.api.deps import get_db
from server.common.response import MessageResponse
from server.schemas.training_block import (
    TrainingBlockCreate,
    TrainingBlockRead,
    TrainingBlockUpdate,
)
from server.services import training_block_service

router = APIRouter(prefix="/training-blocks", tags=["training blocks"])


@router.get("", response_model=list[TrainingBlockRead])
def list_training_blocks(
    cycle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return training_block_service.list_training_blocks(db, cycle_id)


@router.post("", response_model=TrainingBlockRead, status_code=status.HTTP_201_CREATED)
def create_training_block(payload: TrainingBlockCreate, db: Session = Depends(get_db)):
    return training_block_service.create_training_block(db, payload)


@router.get("/{block_id}", response_model=TrainingBlockRead)
def get_training_block(block_id: int, db: Session = Depends(get_db)):
    return training_block_service.get_training_block(db, block_id)


@router.put("/{block_id}", response_model=TrainingBlockRead)
def update_training_block(
    block_id: int,
    payload: TrainingBlockUpdate,
    db: Session = Depends(get_db),
):
    return training_block_service.update_training_block(db, block_id, payload)


@router.delete("/{block_id}", response_model=MessageResponse)
def delete_training_block(block_id: int, db: Session = Depends(get_db)):
    training_block_service.delete_training_block(db, block_id)
    return MessageResponse(message="Training block deleted.")

