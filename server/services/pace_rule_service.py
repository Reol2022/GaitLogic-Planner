from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import PaceRule
from server.common.exceptions import NotFoundError
from server.schemas.pace_rule import PaceRuleCreate, PaceRuleUpdate


def list_pace_rules(db: Session) -> list[PaceRule]:
    return list(db.scalars(select(PaceRule).order_by(PaceRule.sort_order, PaceRule.id)))


def get_pace_rule(db: Session, rule_id: int) -> PaceRule:
    rule = db.get(PaceRule, rule_id)
    if rule is None:
        raise NotFoundError("Pace rule not found.")
    return rule


def create_pace_rule(db: Session, payload: PaceRuleCreate) -> PaceRule:
    rule = PaceRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_pace_rule(db: Session, rule_id: int, payload: PaceRuleUpdate) -> PaceRule:
    rule = get_pace_rule(db, rule_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_pace_rule(db: Session, rule_id: int) -> None:
    rule = get_pace_rule(db, rule_id)
    db.delete(rule)
    db.commit()

