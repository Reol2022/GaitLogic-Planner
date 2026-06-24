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
from server.services import recovery_checkin_service
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
