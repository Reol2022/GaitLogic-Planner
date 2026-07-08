from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.recovery_checkin import (
    RecoveryCheckinListResponse,
    RecoveryCheckinPayload,
    RecoveryCheckinRead,
)
from server.schemas.simplified_workflow import RecoveryQuickPayload, RecoveryQuickRead
from server.services import recovery_checkin_service
from server.services import simplified_workflow_service
from server.services.feature_access_service import assert_training_readiness_available

router = APIRouter(prefix="/recovery-checkins", tags=["recovery checkins"])


def _assert_available(db: Session, current_user: UserAccount) -> None:
    assert_training_readiness_available(db, current_user)


@router.get("/today", response_model=RecoveryCheckinRead | None)
def get_today_recovery_checkin(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    return recovery_checkin_service.get_today_checkin(db, current_user.id)


@router.put("/today", response_model=RecoveryCheckinRead)
def upsert_today_recovery_checkin(
    payload: RecoveryCheckinPayload,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    return recovery_checkin_service.upsert_today_checkin(db, current_user.id, payload)


@router.get("/quick", response_model=RecoveryQuickRead)
def get_quick_recovery_checkin(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RecoveryQuickRead:
    _assert_available(db, current_user)
    return simplified_workflow_service.recovery_quick_from_checkin(
        recovery_checkin_service.get_today_checkin(db, current_user.id)
    )


@router.put("/quick", response_model=RecoveryQuickRead)
def upsert_quick_recovery_checkin(
    payload: RecoveryQuickPayload,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RecoveryQuickRead:
    _assert_available(db, current_user)
    mapped_payload = RecoveryCheckinPayload(
        leg_feeling={"good": 4, "normal": 3, "bad": 2}[payload.leg_feeling],
        subjective_fatigue={"low": 2, "normal": 3, "high": 4}[payload.fatigue],
        pain_level={"none": 0, "mild": 2, "obvious": 5}[payload.pain],
    )
    checkin = recovery_checkin_service.upsert_today_checkin(db, current_user.id, mapped_payload)
    return simplified_workflow_service.recovery_quick_from_checkin(checkin)


@router.delete("/{checkin_date}", response_model=MessageResponse)
def delete_recovery_checkin(
    checkin_date: date,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    recovery_checkin_service.delete_checkin(db, current_user.id, checkin_date)
    return MessageResponse(message="恢复打卡已删除")


@router.get("", response_model=RecoveryCheckinListResponse)
def list_recovery_checkins(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    return RecoveryCheckinListResponse(
        items=recovery_checkin_service.list_checkins(db, current_user.id, start_date, end_date)
    )
