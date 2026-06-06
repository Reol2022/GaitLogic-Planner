from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import PaceRule
from server.common.exceptions import NotFoundError
from server.schemas.pace_rule import PaceRuleCreate, PaceRuleUpdate


def list_pace_rules(db: Session, user_id: int) -> list[PaceRule]:
    return list(
        db.scalars(
            select(PaceRule)
            .where(PaceRule.user_id == user_id)
            .order_by(PaceRule.sort_order, PaceRule.id)
        )
    )


def get_pace_rule(db: Session, rule_id: int, user_id: int) -> PaceRule:
    rule = db.scalar(
        select(PaceRule).where(PaceRule.id == rule_id, PaceRule.user_id == user_id)
    )
    if rule is None:
        raise NotFoundError("Pace rule not found.")
    return rule


def create_pace_rule(db: Session, payload: PaceRuleCreate, user_id: int) -> PaceRule:
    rule = PaceRule(**payload.model_dump(), user_id=user_id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_pace_rule(
    db: Session,
    rule_id: int,
    payload: PaceRuleUpdate,
    user_id: int,
) -> PaceRule:
    rule = get_pace_rule(db, rule_id, user_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_pace_rule(db: Session, rule_id: int, user_id: int) -> None:
    rule = get_pace_rule(db, rule_id, user_id)
    db.delete(rule)
    db.commit()
