from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.onboarding import OnboardingStatusRead
from server.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusRead)
def get_onboarding_status(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return onboarding_service.get_onboarding_status(db, current_user.id)
