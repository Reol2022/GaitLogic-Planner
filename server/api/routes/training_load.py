from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.training_readiness import (
    TrainingLoadDailyResponse,
    TrainingLoadSummaryResponse,
    TrainingLoadTrendResponse,
)
from server.services.feature_access_service import assert_training_readiness_available
from server.services.training_load_service import build_daily_training_loads, build_training_load_summary
from server.services.weekly_review_stats_service import local_today

router = APIRouter(prefix="/training-load", tags=["training load"])


def _assert_available(db: Session, current_user: UserAccount) -> None:
    assert_training_readiness_available(db, current_user)


@router.get("/summary", response_model=TrainingLoadSummaryResponse)
def get_training_load_summary(
    date_: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    return TrainingLoadSummaryResponse(summary=build_training_load_summary(db, current_user.id, date_))


@router.get("/daily", response_model=TrainingLoadDailyResponse)
def get_daily_training_load(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    end = end_date or local_today()
    start = start_date or (end - timedelta(days=41))
    return TrainingLoadDailyResponse(items=build_daily_training_loads(db, current_user.id, start, end))


@router.get("/trend", response_model=TrainingLoadTrendResponse)
def get_training_load_trend(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    _assert_available(db, current_user)
    end = end_date or local_today()
    start = start_date or (end - timedelta(days=41))
    return TrainingLoadTrendResponse(
        start_date=start,
        end_date=end,
        items=build_daily_training_loads(db, current_user.id, start, end),
    )
