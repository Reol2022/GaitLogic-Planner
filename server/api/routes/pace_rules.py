from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from server.api.deps import get_db
from server.common.response import MessageResponse
from server.schemas.pace_rule import PaceRuleCreate, PaceRuleRead, PaceRuleUpdate
from server.services import pace_rule_service

router = APIRouter(prefix="/pace-rules", tags=["pace rules"])


@router.get("", response_model=list[PaceRuleRead])
def list_pace_rules(db: Session = Depends(get_db)):
    return pace_rule_service.list_pace_rules(db)


@router.post("", response_model=PaceRuleRead, status_code=status.HTTP_201_CREATED)
def create_pace_rule(payload: PaceRuleCreate, db: Session = Depends(get_db)):
    return pace_rule_service.create_pace_rule(db, payload)


@router.put("/{rule_id}", response_model=PaceRuleRead)
def update_pace_rule(
    rule_id: int,
    payload: PaceRuleUpdate,
    db: Session = Depends(get_db),
):
    return pace_rule_service.update_pace_rule(db, rule_id, payload)


@router.delete("/{rule_id}", response_model=MessageResponse)
def delete_pace_rule(rule_id: int, db: Session = Depends(get_db)):
    pace_rule_service.delete_pace_rule(db, rule_id)
    return MessageResponse(message="Pace rule deleted.")

