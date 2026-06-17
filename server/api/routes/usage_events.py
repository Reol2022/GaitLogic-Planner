from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.usage_event import UsageEventAck, UsageEventCreate
from server.services import usage_event_service

router = APIRouter(prefix="/usage-events", tags=["usage events"])


@router.post("", response_model=UsageEventAck)
def create_usage_event(
    payload: UsageEventCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    usage_event_service.record_usage_event(db, current_user.id, payload)
    return UsageEventAck()
