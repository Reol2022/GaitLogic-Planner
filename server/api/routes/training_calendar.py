from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.training_calendar import TrainingCalendarRead
from server.services import training_calendar_service

router = APIRouter(tags=["training calendar"])


@router.get("/training-calendar", response_model=TrainingCalendarRead)
def get_training_calendar(
    cycle_id: int | None = Query(default=None),
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_calendar_service.get_training_calendar(
        db,
        current_user.id,
        cycle_id=cycle_id,
        month=month,
    )
