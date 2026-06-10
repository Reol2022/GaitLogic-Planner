from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.ai_coach_preference import AICoachPreferenceRead, AICoachPreferenceUpdate
from server.services import ai_coach_preference_service

router = APIRouter(prefix="/ai-coach-preference", tags=["AI coach preference"])


@router.get("", response_model=AICoachPreferenceRead)
def get_ai_coach_preference(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return ai_coach_preference_service.get_or_create_preference(db, current_user.id)


@router.put("", response_model=AICoachPreferenceRead)
def update_ai_coach_preference(
    payload: AICoachPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return ai_coach_preference_service.update_preference(db, current_user.id, payload)
