from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import TrainingRule, TrainingRuleEvaluation, TrainingRuleHit
from planner_core.training_knowledge.rule_engine import DEFAULT_RULESET_VERSION, TrainingRuleEngine
from planner_core.training_knowledge.schemas import (
    ApplicabilityDefinition,
    RuleResultDefinition,
    ThresholdDefinition,
    TrainingRuleDefinition,
)
from planner_core.training_knowledge.validators import validate_rule_definition
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.training_rules import (
    TrainingRuleEvaluateRequest,
    TrainingRuleEvaluateResponse,
    TrainingRuleRead,
)
from server.services.training_facts.common import SOURCE_VERSION, hash_facts


def _rule_model_to_definition(rule: TrainingRule) -> TrainingRuleDefinition:
    return TrainingRuleDefinition(
        code=rule.code,
        name=rule.name,
        description=rule.description,
        category=rule.category,
        scope=rule.scope,
        conditions=rule.conditions_json,
        result=RuleResultDefinition.model_validate(rule.result_json),
        explanation_template=rule.explanation_template,
        severity=rule.severity,
        priority=rule.priority,
        evidence_refs=rule.evidence_refs_json or [],
        applicability=ApplicabilityDefinition.model_validate(rule.applicability_json or {}),
        thresholds=[ThresholdDefinition.model_validate(item) for item in (rule.thresholds_json or [])],
        version=rule.version,
        enabled=rule.enabled,
        public=rule.public,
        source_type=rule.source_type,
        lifecycle_status=rule.lifecycle_status,
    )


def _rule_to_read(rule: TrainingRule, *, reveal_definition: bool) -> TrainingRuleRead:
    return TrainingRuleRead(
        id=rule.id,
        code=rule.code,
        name=rule.name,
        description=rule.description,
        category=rule.category,
        scope=rule.scope,
        severity=rule.severity,
        priority=rule.priority,
        evidence_refs_json=rule.evidence_refs_json or [],
        version=rule.version,
        enabled=rule.enabled,
        public=rule.public,
        source_type=rule.source_type,
        lifecycle_status=rule.lifecycle_status,
        current_version=rule.current_version,
        applicability_json=rule.applicability_json or {},
        thresholds_json=rule.thresholds_json or [],
        conditions_json=rule.conditions_json if reveal_definition else None,
        result_json=rule.result_json if reveal_definition else None,
        explanation_template=rule.explanation_template if reveal_definition else None,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def list_rules(
    db: Session,
    *,
    is_admin: bool,
    category: str | None = None,
    scope: str | None = None,
    severity: str | None = None,
    enabled: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TrainingRuleRead], int]:
    stmt = select(TrainingRule)
    count_stmt = select(func.count()).select_from(TrainingRule)
    predicates = []
    if not is_admin:
        predicates.extend([TrainingRule.enabled.is_(True), TrainingRule.public.is_(True)])
    elif enabled is not None:
        predicates.append(TrainingRule.enabled.is_(enabled))
    if category:
        predicates.append(TrainingRule.category == category)
    if scope:
        predicates.append(TrainingRule.scope == scope)
    if severity:
        predicates.append(TrainingRule.severity == severity)
    for predicate in predicates:
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)
    total = db.scalar(count_stmt) or 0
    rules = list(
        db.scalars(
            stmt.order_by(TrainingRule.category, TrainingRule.scope, TrainingRule.code)
            .limit(limit)
            .offset(offset)
        )
    )
    return [_rule_to_read(rule, reveal_definition=is_admin or rule.public) for rule in rules], total


def get_rule(db: Session, code: str, *, is_admin: bool) -> TrainingRuleRead:
    stmt = select(TrainingRule).where(TrainingRule.code == code)
    if not is_admin:
        stmt = stmt.where(TrainingRule.enabled.is_(True), TrainingRule.public.is_(True))
    rule = db.scalar(stmt)
    if rule is None:
        raise NotFoundError("Training rule not found.")
    return _rule_to_read(rule, reveal_definition=is_admin or rule.public)


def set_rule_enabled(db: Session, code: str, enabled: bool) -> TrainingRuleRead:
    rule = db.scalar(select(TrainingRule).where(TrainingRule.code == code))
    if rule is None:
        raise NotFoundError("Training rule not found.")
    rule.enabled = enabled
    db.commit()
    db.refresh(rule)
    return _rule_to_read(rule, reveal_definition=True)


def validate_rule_payload(definition: dict[str, Any]) -> TrainingRuleDefinition:
    try:
        return validate_rule_definition(definition)
    except ValueError as exc:
        raise BadRequestError(f"Invalid training rule definition: {exc}") from exc


def evaluate_rules(
    db: Session,
    *,
    user_id: int,
    payload: TrainingRuleEvaluateRequest,
) -> TrainingRuleEvaluateResponse:
    rules = [
        _rule_model_to_definition(rule)
        for rule in db.scalars(select(TrainingRule).where(TrainingRule.enabled.is_(True)))
    ]
    result = TrainingRuleEngine(ruleset_version=DEFAULT_RULESET_VERSION).evaluate(
        facts=payload.facts,
        rules=rules,
        context_type=payload.context_type,
    )
    evaluation_id: int | None = None
    if payload.persist:
        evaluation = TrainingRuleEvaluation(
            user_id=user_id,
            context_type=payload.context_type,
            context_id=payload.context_id,
            input_snapshot_json=payload.facts,
            final_result_json=result.model_dump(mode="json"),
            dominant_rule_code=result.dominant_rule_code,
            engine_version=result.engine_version,
            ruleset_version=result.ruleset_version,
        )
        db.add(evaluation)
        db.flush()
        for hit in result.matched_rules:
            db.add(
                TrainingRuleHit(
                    evaluation_id=evaluation.id,
                    rule_code=hit.rule_code,
                    rule_version=hit.rule_version,
                    matched=hit.matched,
                    severity=hit.severity,
                    priority=hit.priority,
                    input_snapshot_json=payload.facts,
                    output_json=hit.output,
                    explanation=hit.explanation,
                )
            )
        db.commit()
        evaluation_id = evaluation.id
    return TrainingRuleEvaluateResponse.from_engine_result(result, evaluation_id=evaluation_id)


def evaluate_standard_facts(
    db: Session,
    *,
    user_id: int,
    context_type: str,
    context_id: str | None,
    facts: dict[str, Any],
    persist: bool = True,
    force: bool = False,
    source_version: str = SOURCE_VERSION,
) -> tuple[TrainingRuleEvaluateResponse, TrainingRuleEvaluation | None]:
    facts_digest = hash_facts(facts)
    if persist and not force:
        existing = db.scalar(
            select(TrainingRuleEvaluation)
            .where(
                TrainingRuleEvaluation.user_id == user_id,
                TrainingRuleEvaluation.context_type == context_type,
                TrainingRuleEvaluation.context_id == context_id,
                TrainingRuleEvaluation.facts_hash == facts_digest,
                TrainingRuleEvaluation.source_version == source_version,
                TrainingRuleEvaluation.ruleset_version == DEFAULT_RULESET_VERSION,
                TrainingRuleEvaluation.is_stale.is_(False),
            )
            .order_by(TrainingRuleEvaluation.created_at.desc(), TrainingRuleEvaluation.id.desc())
            .limit(1)
        )
        if existing is not None:
            final = dict(existing.final_result_json or {})
            final["evaluation_id"] = existing.id
            response = TrainingRuleEvaluateResponse.model_validate(final)
            return response, existing
    mark_stale_for_context(
        db,
        user_id=user_id,
        context_type=context_type,
        context_id=context_id,
        stale_reason="replaced_by_new_evaluation",
    )
    rules = [
        _rule_model_to_definition(rule)
        for rule in db.scalars(select(TrainingRule).where(TrainingRule.enabled.is_(True)))
    ]
    result = TrainingRuleEngine(ruleset_version=DEFAULT_RULESET_VERSION).evaluate(
        facts=facts,
        rules=rules,
        context_type=context_type,
    )
    evaluation: TrainingRuleEvaluation | None = None
    if persist:
        evaluation = TrainingRuleEvaluation(
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
            input_snapshot_json=facts,
            final_result_json=result.model_dump(mode="json"),
            dominant_rule_code=result.dominant_rule_code,
            engine_version=result.engine_version,
            ruleset_version=result.ruleset_version,
            facts_hash=facts_digest,
            source_version=source_version,
        )
        db.add(evaluation)
        db.flush()
        for hit in result.matched_rules:
            db.add(
                TrainingRuleHit(
                    evaluation_id=evaluation.id,
                    rule_code=hit.rule_code,
                    rule_version=hit.rule_version,
                    matched=hit.matched,
                    severity=hit.severity,
                    priority=hit.priority,
                    input_snapshot_json=facts,
                    output_json=hit.output,
                    explanation=hit.explanation,
                )
            )
        db.commit()
    return TrainingRuleEvaluateResponse.from_engine_result(result, evaluation_id=evaluation.id if evaluation else None), evaluation


def mark_stale_for_context(
    db: Session,
    *,
    user_id: int,
    context_type: str,
    context_id: str | None,
    stale_reason: str,
) -> int:
    rows = list(
        db.scalars(
            select(TrainingRuleEvaluation).where(
                TrainingRuleEvaluation.user_id == user_id,
                TrainingRuleEvaluation.context_type == context_type,
                TrainingRuleEvaluation.context_id == context_id,
                TrainingRuleEvaluation.is_stale.is_(False),
            )
        )
    )
    for row in rows:
        row.is_stale = True
        row.stale_reason = stale_reason
    return len(rows)


def list_evaluations(
    db: Session,
    *,
    user_id: int,
    is_admin: bool,
    context_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TrainingRuleEvaluation], int]:
    stmt = select(TrainingRuleEvaluation)
    count_stmt = select(func.count()).select_from(TrainingRuleEvaluation)
    predicates = []
    if not is_admin:
        predicates.append(TrainingRuleEvaluation.user_id == user_id)
    if context_type:
        predicates.append(TrainingRuleEvaluation.context_type == context_type)
    for predicate in predicates:
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(TrainingRuleEvaluation.created_at.desc(), TrainingRuleEvaluation.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def get_evaluation(
    db: Session,
    evaluation_id: int,
    *,
    user_id: int,
    is_admin: bool,
) -> TrainingRuleEvaluation:
    stmt = (
        select(TrainingRuleEvaluation)
        .options(selectinload(TrainingRuleEvaluation.hits))
        .where(TrainingRuleEvaluation.id == evaluation_id)
    )
    if not is_admin:
        stmt = stmt.where(TrainingRuleEvaluation.user_id == user_id)
    evaluation = db.scalar(stmt)
    if evaluation is None:
        raise NotFoundError("Training rule evaluation not found.")
    return evaluation
