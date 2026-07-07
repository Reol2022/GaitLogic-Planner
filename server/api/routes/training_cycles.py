from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.training_cycle import (
    TrainingCycleActivateRequest,
    TrainingCycleActivationPreview,
    TrainingCycleCompleteRequest,
    TrainingCycleCreate,
    TrainingCycleRead,
    TrainingCycleUpdate,
)
from server.services import training_cycle_lifecycle_service, training_cycle_service

router = APIRouter(prefix="/training-cycles", tags=["training cycles"])


@router.get("", response_model=list[TrainingCycleRead])
def list_training_cycles(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_service.list_training_cycles(db, current_user.id)


@router.get("/active", response_model=TrainingCycleRead)
def get_active_cycle(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_service.get_active_cycle(db, current_user.id)


@router.get("/history", response_model=list[TrainingCycleRead])
def list_history_cycles(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_service.list_history_cycles(db, current_user.id)


@router.post("", response_model=TrainingCycleRead, status_code=status.HTTP_201_CREATED)
def create_training_cycle(
    payload: TrainingCycleCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_service.create_training_cycle(db, payload, current_user.id)


@router.get("/{cycle_id}/activation-preview", response_model=TrainingCycleActivationPreview)
def get_activation_preview(
    cycle_id: int,
    effective_start_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_lifecycle_service.activation_preview(db, current_user.id, cycle_id, effective_start_date)


@router.post("/{cycle_id}/activate", response_model=TrainingCycleRead)
def activate_cycle(
    cycle_id: int,
    payload: TrainingCycleActivateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_lifecycle_service.activate_cycle(db, current_user.id, cycle_id, payload)


@router.post("/{cycle_id}/complete", response_model=TrainingCycleRead)
def complete_cycle(
    cycle_id: int,
    payload: TrainingCycleCompleteRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_lifecycle_service.complete_cycle(db, current_user.id, cycle_id, payload)


@router.post("/{cycle_id}/archive", response_model=TrainingCycleRead)
def archive_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_lifecycle_service.archive_cycle(db, current_user.id, cycle_id)


@router.get("/{cycle_id}", response_model=TrainingCycleRead)
def get_training_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_service.get_training_cycle(db, cycle_id, current_user.id)


@router.put("/{cycle_id}", response_model=TrainingCycleRead)
def update_training_cycle(
    cycle_id: int,
    payload: TrainingCycleUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_cycle_service.update_training_cycle(db, cycle_id, payload, current_user.id)


@router.delete("/{cycle_id}", response_model=MessageResponse)
def delete_training_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    training_cycle_service.delete_training_cycle(db, cycle_id, current_user.id)
    return MessageResponse(message="Training cycle deleted.")
