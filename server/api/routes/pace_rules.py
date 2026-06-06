from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.pace_rule import PaceRuleCreate, PaceRuleRead, PaceRuleUpdate
from server.services import pace_rule_service

router = APIRouter(prefix="/pace-rules", tags=["pace rules"])


@router.get("", response_model=list[PaceRuleRead])
def list_pace_rules(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return pace_rule_service.list_pace_rules(db, current_user.id)


@router.post("", response_model=PaceRuleRead, status_code=status.HTTP_201_CREATED)
def create_pace_rule(
    payload: PaceRuleCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return pace_rule_service.create_pace_rule(db, payload, current_user.id)


@router.put("/{rule_id}", response_model=PaceRuleRead)
def update_pace_rule(
    rule_id: int,
    payload: PaceRuleUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return pace_rule_service.update_pace_rule(db, rule_id, payload, current_user.id)


@router.delete("/{rule_id}", response_model=MessageResponse)
def delete_pace_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    pace_rule_service.delete_pace_rule(db, rule_id, current_user.id)
    return MessageResponse(message="Pace rule deleted.")
