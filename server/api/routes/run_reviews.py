from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.run_review import RunReviewRead
from server.services.run_review_service import get_run_review

router = APIRouter(prefix="/run-reviews", tags=["run reviews"])


@router.get("/activities/{activity_id}", response_model=RunReviewRead)
def get_activity_run_review(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> RunReviewRead:
    return get_run_review(db, user_id=current_user.id, activity_id=activity_id)
