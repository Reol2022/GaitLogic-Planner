from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from server.api.deps import get_db
from server.common.response import MessageResponse
from server.schemas.training_cycle import (
    TrainingCycleCreate,
    TrainingCycleRead,
    TrainingCycleUpdate,
)
from server.services import training_cycle_service

router = APIRouter(prefix="/training-cycles", tags=["training cycles"])


@router.get("", response_model=list[TrainingCycleRead])
def list_training_cycles(db: Session = Depends(get_db)):
    return training_cycle_service.list_training_cycles(db)


@router.post("", response_model=TrainingCycleRead, status_code=status.HTTP_201_CREATED)
def create_training_cycle(payload: TrainingCycleCreate, db: Session = Depends(get_db)):
    return training_cycle_service.create_training_cycle(db, payload)


@router.get("/{cycle_id}", response_model=TrainingCycleRead)
def get_training_cycle(cycle_id: int, db: Session = Depends(get_db)):
    return training_cycle_service.get_training_cycle(db, cycle_id)


@router.put("/{cycle_id}", response_model=TrainingCycleRead)
def update_training_cycle(
    cycle_id: int,
    payload: TrainingCycleUpdate,
    db: Session = Depends(get_db),
):
    return training_cycle_service.update_training_cycle(db, cycle_id, payload)


@router.delete("/{cycle_id}", response_model=MessageResponse)
def delete_training_cycle(cycle_id: int, db: Session = Depends(get_db)):
    training_cycle_service.delete_training_cycle(db, cycle_id)
    return MessageResponse(message="Training cycle deleted.")

