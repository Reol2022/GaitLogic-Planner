from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.training_readiness import (
    TrainingReadinessHistoryResponse,
    TrainingReadinessTodayResponse,
)
from server.services import readiness_assessment_service, recovery_checkin_service
from server.services.feature_access_service import assert_training_readiness_available
from server.services.weekly_review_stats_service import local_today

router = APIRouter(prefix="/training-readiness", tags=["training readiness"])


def _assert_available(db: Session, current_user: UserAccount) -> None:
    assert_training_readiness_available(db, current_user)


@router.get("/today", response_model=TrainingReadinessTodayResponse)
def get_today_readiness(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    assessment = readiness_assessment_service.get_or_create_today_assessment(db, current_user.id)
    return TrainingReadinessTodayResponse(
        assessment=assessment,
        recovery_checkin_completed=bool(recovery_checkin_service.get_today_checkin(db, current_user.id)),
    )


@router.post("/recalculate", response_model=TrainingReadinessTodayResponse)
def recalculate_readiness(
    date_: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    assessment_date = date_ or local_today()
    assessment = readiness_assessment_service.evaluate_and_save_readiness(db, current_user.id, assessment_date)
    return TrainingReadinessTodayResponse(
        assessment=assessment,
        recovery_checkin_completed=bool(recovery_checkin_service.get_checkin(db, current_user.id, assessment_date)),
    )


@router.get("/history", response_model=TrainingReadinessHistoryResponse)
def list_readiness_history(
    days: int = Query(default=30, ge=1, le=120),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    return TrainingReadinessHistoryResponse(
        items=readiness_assessment_service.list_assessments(db, current_user.id, days)
    )


@router.get("/{assessment_date}", response_model=TrainingReadinessTodayResponse)
def get_readiness_by_date(
    assessment_date: date,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    assessment = readiness_assessment_service.get_assessment_by_date(db, current_user.id, assessment_date)
    return TrainingReadinessTodayResponse(
        assessment=assessment,
        recovery_checkin_completed=bool(recovery_checkin_service.get_checkin(db, current_user.id, assessment_date)),
    )
