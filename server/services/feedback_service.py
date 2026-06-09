from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import Feedback
from server.schemas.feedback import FeedbackCreate


def create_feedback(db: Session, payload: FeedbackCreate, user_id: int) -> Feedback:
    feedback = Feedback(**payload.model_dump(), user_id=user_id, status="open")
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_my_feedback(db: Session, user_id: int) -> list[Feedback]:
    return list(
        db.scalars(
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        )
    )
