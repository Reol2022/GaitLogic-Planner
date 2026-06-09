from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.feedback import FeedbackCreate, FeedbackRead
from server.services import feedback_service

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    feedback_service.create_feedback(db, payload, current_user.id)
    return MessageResponse(message="反馈提交成功")


@router.get("/my", response_model=list[FeedbackRead])
def list_my_feedback(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return feedback_service.list_my_feedback(db, current_user.id)
