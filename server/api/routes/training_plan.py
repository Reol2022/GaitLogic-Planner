from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.simplified_workflow import TrainingPlanOverviewRead
from server.services import simplified_workflow_service
from server.services.feature_access_service import assert_simplified_workflow_available

router = APIRouter(prefix="/training-plan", tags=["training plan center"])


@router.get("/overview", response_model=TrainingPlanOverviewRead)
def get_training_plan_overview(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> TrainingPlanOverviewRead:
    assert_simplified_workflow_available(db, current_user)
    return simplified_workflow_service.get_training_plan_overview(db, current_user.id)
