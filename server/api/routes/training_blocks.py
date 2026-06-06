from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
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
    current_user: UserAccount = Depends(get_current_user),
):
    return training_block_service.list_training_blocks(db, current_user.id, cycle_id)


@router.post("", response_model=TrainingBlockRead, status_code=status.HTTP_201_CREATED)
def create_training_block(
    payload: TrainingBlockCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_block_service.create_training_block(db, payload, current_user.id)


@router.get("/{block_id}", response_model=TrainingBlockRead)
def get_training_block(
    block_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_block_service.get_training_block(db, block_id, current_user.id)


@router.put("/{block_id}", response_model=TrainingBlockRead)
def update_training_block(
    block_id: int,
    payload: TrainingBlockUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_block_service.update_training_block(db, block_id, payload, current_user.id)


@router.delete("/{block_id}", response_model=MessageResponse)
def delete_training_block(
    block_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    training_block_service.delete_training_block(db, block_id, current_user.id)
    return MessageResponse(message="Training block deleted.")
