from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner_core.database.models import (
    TrainingEvidenceSource,
    TrainingRule,
    TrainingRuleAuditLog,
    TrainingRuleEvaluation,
    TrainingRuleEvidenceLink,
    TrainingRuleHit,
    TrainingRuleReview,
    TrainingRuleTestCase,
    TrainingRuleTestResult,
    TrainingRuleTestRun,
    TrainingRuleVersion,
)
from planner_core.training_knowledge.governance import (
    content_hash,
    diff_results,
    rule_content_payload,
    validate_lifecycle_transition,
    validate_threshold_declarations,
)
from planner_core.training_knowledge.enums import RuleLifecycleStatus
from planner_core.training_knowledge.rule_engine import DEFAULT_RULESET_VERSION, TrainingRuleEngine
from planner_core.training_knowledge.schemas import (
    ApplicabilityDefinition,
    RuleResultDefinition,
    ThresholdDefinition,
    TrainingRuleDefinition,
)
from planner_core.training_knowledge.validators import validate_rule_definition
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.training_rule_governance import (
    EvidenceSourceCreate,
    EvidenceSourceUpdate,
    ImpactAnalysisRead,
    RuleTestRunRequest,
    RuleVersionCreate,
)


def _audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_code: str | None = None,
    target_version: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        TrainingRuleAuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_code=target_code,
            target_version=target_version,
            before_snapshot_json=before,
            after_snapshot_json=after,
            reason=reason,
        )
    )


def _source_type_to_evidence_level(source_type: str) -> str:
    if source_type in {"safety_boundary", "system_default"}:
        return "not_applicable"
    if source_type == "product_rule":
        return "product_assumption"
    return "limited"


def _version_to_definition(version: TrainingRuleVersion, *, enabled: bool = True, public: bool = True) -> TrainingRuleDefinition:
    return TrainingRuleDefinition(
        code=version.rule_code,
        name=version.name,
        description=version.description,
        category=version.category,
        scope=version.scope,
        conditions=version.conditions_json,
        result=RuleResultDefinition.model_validate(version.result_json),
        applicability=ApplicabilityDefinition.model_validate(version.applicability_json or {}),
        thresholds=[ThresholdDefinition.model_validate(item) for item in (version.thresholds_json or [])],
        explanation_template=version.explanation_template,
        severity=version.severity,
        priority=version.priority,
        version=version.version,
        enabled=enabled,
        public=public,
        source_type=version.source_type,
        lifecycle_status=version.lifecycle_status,
    )


def _rule_to_definition(rule: TrainingRule) -> TrainingRuleDefinition:
    return TrainingRuleDefinition(
        code=rule.code,
        name=rule.name,
        description=rule.description,
        category=rule.category,
        scope=rule.scope,
        conditions=rule.conditions_json,
        result=RuleResultDefinition.model_validate(rule.result_json),
        applicability=ApplicabilityDefinition.model_validate(rule.applicability_json or {}),
        thresholds=[ThresholdDefinition.model_validate(item) for item in (rule.thresholds_json or [])],
        explanation_template=rule.explanation_template,
        severity=rule.severity,
        priority=rule.priority,
        version=rule.version,
        enabled=rule.enabled,
        public=rule.public,
        source_type=rule.source_type,
        lifecycle_status=rule.lifecycle_status,
    )


def _published_rules(db: Session) -> list[TrainingRuleDefinition]:
    return [
        _rule_to_definition(rule)
        for rule in db.scalars(
            select(TrainingRule).where(
                TrainingRule.enabled.is_(True),
                TrainingRule.lifecycle_status == "published",
            )
        )
    ]


def list_evidence(db: Session) -> list[TrainingEvidenceSource]:
    return list(db.scalars(select(TrainingEvidenceSource).order_by(TrainingEvidenceSource.code)))


def create_evidence(db: Session, payload: EvidenceSourceCreate, actor_user_id: int) -> TrainingEvidenceSource:
    existing = db.scalar(select(TrainingEvidenceSource).where(TrainingEvidenceSource.code == payload.code))
    if existing is not None:
        raise BadRequestError("Evidence source code already exists.")
    row = TrainingEvidenceSource(**payload.model_dump())
    db.add(row)
    db.flush()
    _audit(db, actor_user_id=actor_user_id, action="create_evidence", target_type="evidence", target_code=row.code, after=payload.model_dump())
    db.commit()
    db.refresh(row)
    return row


def get_evidence(db: Session, code: str, *, public: bool = False) -> TrainingEvidenceSource:
    row = db.scalar(select(TrainingEvidenceSource).where(TrainingEvidenceSource.code == code))
    if row is None or (public and row.review_status not in {"verified", "deprecated"}):
        raise NotFoundError("Evidence source not found.")
    return row


def update_evidence(db: Session, code: str, payload: EvidenceSourceUpdate, actor_user_id: int) -> TrainingEvidenceSource:
    row = get_evidence(db, code)
    before = {"code": row.code, "title": row.title, "review_status": row.review_status}
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    _audit(db, actor_user_id=actor_user_id, action="update_evidence", target_type="evidence", target_code=row.code, before=before, after=data)
    db.commit()
    db.refresh(row)
    return row


def archive_evidence(db: Session, code: str, actor_user_id: int) -> TrainingEvidenceSource:
    row = get_evidence(db, code)
    before = {"review_status": row.review_status}
    row.review_status = "archived"
    _audit(db, actor_user_id=actor_user_id, action="archive_evidence", target_type="evidence", target_code=code, before=before, after={"review_status": "archived"})
    db.commit()
    db.refresh(row)
    return row


def list_versions(db: Session, rule_code: str) -> list[TrainingRuleVersion]:
    return list(db.scalars(select(TrainingRuleVersion).where(TrainingRuleVersion.rule_code == rule_code).order_by(TrainingRuleVersion.created_at.desc(), TrainingRuleVersion.version.desc())))


def get_version(db: Session, rule_code: str, version: str) -> TrainingRuleVersion:
    row = db.scalar(select(TrainingRuleVersion).where(TrainingRuleVersion.rule_code == rule_code, TrainingRuleVersion.version == version))
    if row is None:
        raise NotFoundError("Training rule version not found.")
    return row


def _validate_version_payload(rule_code: str, payload: RuleVersionCreate) -> TrainingRuleDefinition:
    definition = {
        "code": rule_code,
        "name": payload.name,
        "description": payload.description,
        "category": payload.category,
        "scope": payload.scope,
        "conditions": payload.conditions_json,
        "result": payload.result_json,
        "applicability": payload.applicability_json or {},
        "thresholds": payload.thresholds_json or [],
        "explanation_template": payload.explanation_template,
        "severity": payload.severity,
        "priority": payload.priority,
        "version": payload.version,
        "enabled": False,
        "public": True,
        "source_type": payload.source_type,
        "lifecycle_status": "draft",
    }
    rule = validate_rule_definition(definition)
    threshold_errors = validate_threshold_declarations(rule)
    if threshold_errors:
        raise BadRequestError("; ".join(threshold_errors))
    return rule


def create_version(db: Session, rule_code: str, payload: RuleVersionCreate, actor_user_id: int) -> TrainingRuleVersion:
    rule = _validate_version_payload(rule_code, payload)
    if db.scalar(select(TrainingRuleVersion).where(TrainingRuleVersion.rule_code == rule_code, TrainingRuleVersion.version == payload.version)):
        raise BadRequestError("Training rule version already exists.")
    row = TrainingRuleVersion(
        rule_code=rule_code,
        version=payload.version,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        scope=payload.scope,
        conditions_json=payload.conditions_json,
        result_json=payload.result_json,
        applicability_json=rule.applicability.model_dump(mode="json"),
        thresholds_json=[item.model_dump(mode="json") for item in rule.thresholds],
        explanation_template=payload.explanation_template,
        severity=payload.severity,
        priority=payload.priority,
        source_type=payload.source_type,
        lifecycle_status="draft",
        content_hash=content_hash(rule_content_payload(rule)),
        change_summary=payload.change_summary,
        created_by=actor_user_id,
    )
    db.add(row)
    for link in payload.evidence_links:
        relationship_type = link.get("relationship_type")
        source_code = link.get("evidence_source_code")
        support_note = link.get("support_note")
        if not relationship_type or not source_code or not support_note:
            raise BadRequestError("Evidence links require source code, relationship type, and support note.")
        db.add(
            TrainingRuleEvidenceLink(
                rule_code=rule_code,
                rule_version=payload.version,
                evidence_source_code=source_code,
                relationship_type=relationship_type,
                support_note=support_note,
            )
        )
    _audit(db, actor_user_id=actor_user_id, action="create_rule_version", target_type="rule_version", target_code=rule_code, target_version=payload.version, after=payload.model_dump())
    db.commit()
    db.refresh(row)
    return row


def submit_review(db: Session, rule_code: str, version: str, actor_user_id: int) -> TrainingRuleVersion:
    row = get_version(db, rule_code, version)
    validate_lifecycle_transition(row.lifecycle_status, "in_review")
    row.lifecycle_status = "in_review"
    db.add(TrainingRuleReview(rule_code=rule_code, rule_version=version, reviewer_id=None, review_status="pending", checklist_json={}))
    _audit(db, actor_user_id=actor_user_id, action="submit_review", target_type="rule_version", target_code=rule_code, target_version=version)
    db.commit()
    db.refresh(row)
    return row


def list_reviews(db: Session) -> list[TrainingRuleReview]:
    return list(db.scalars(select(TrainingRuleReview).order_by(TrainingRuleReview.created_at.desc(), TrainingRuleReview.id.desc())))


def get_review(db: Session, review_id: int) -> TrainingRuleReview:
    row = db.get(TrainingRuleReview, review_id)
    if row is None:
        raise NotFoundError("Training rule review not found.")
    return row


def review_action(db: Session, review_id: int, actor_user_id: int, status: str, comment: str | None, checklist: dict[str, Any]) -> TrainingRuleReview:
    review = get_review(db, review_id)
    version = get_version(db, review.rule_code, review.rule_version)
    if version.created_by == actor_user_id:
        raise BadRequestError("Rule author cannot review the same version.")
    if status == "approved":
        validate_lifecycle_transition(version.lifecycle_status, "approved")
        version.lifecycle_status = "approved"
        action = "approve"
    elif status == "rejected":
        validate_lifecycle_transition(version.lifecycle_status, "rejected")
        version.lifecycle_status = "rejected"
        action = "reject"
    else:
        status = "changes_requested"
        action = "request_changes"
    review.review_status = status
    review.reviewer_id = actor_user_id
    review.review_comment = comment
    review.checklist_json = checklist or {}
    _audit(db, actor_user_id=actor_user_id, action=action, target_type="rule_review", target_code=review.rule_code, target_version=review.rule_version, reason=comment)
    db.commit()
    db.refresh(review)
    return review


def _latest_successful_test_run(db: Session, rule_code: str | None = None) -> TrainingRuleTestRun | None:
    stmt = select(TrainingRuleTestRun).where(TrainingRuleTestRun.status == "passed")
    return db.scalar(stmt.order_by(TrainingRuleTestRun.finished_at.desc(), TrainingRuleTestRun.id.desc()).limit(1))


def publish_version(db: Session, rule_code: str, version: str, actor_user_id: int) -> TrainingRuleVersion:
    row = get_version(db, rule_code, version)
    if row.lifecycle_status != "approved":
        raise BadRequestError("Only approved versions can be published.")
    approved_review = db.scalar(
        select(TrainingRuleReview).where(
            TrainingRuleReview.rule_code == rule_code,
            TrainingRuleReview.rule_version == version,
            TrainingRuleReview.review_status == "approved",
        )
    )
    if approved_review is None:
        raise BadRequestError("Approved review is required before publishing.")
    if _latest_successful_test_run(db, rule_code) is None:
        raise BadRequestError("Successful rule regression test run is required before publishing.")
    existing_current = db.scalar(select(TrainingRule).where(TrainingRule.code == rule_code))
    old_published = list(db.scalars(select(TrainingRuleVersion).where(TrainingRuleVersion.rule_code == rule_code, TrainingRuleVersion.lifecycle_status == "published")))
    for item in old_published:
        item.lifecycle_status = "deprecated"
    row.lifecycle_status = "published"
    row.published_at = datetime.utcnow()
    if existing_current is None:
        existing_current = TrainingRule(code=rule_code)
        db.add(existing_current)
    existing_current.name = row.name
    existing_current.description = row.description
    existing_current.category = row.category
    existing_current.scope = row.scope
    existing_current.conditions_json = row.conditions_json
    existing_current.result_json = row.result_json
    existing_current.applicability_json = row.applicability_json
    existing_current.thresholds_json = row.thresholds_json
    existing_current.explanation_template = row.explanation_template
    existing_current.severity = row.severity
    existing_current.priority = row.priority
    existing_current.version = row.version
    existing_current.current_version = row.version
    existing_current.current_version_id = row.id
    existing_current.enabled = True
    existing_current.public = True
    existing_current.source_type = row.source_type
    existing_current.lifecycle_status = "published"
    _audit(db, actor_user_id=actor_user_id, action="publish", target_type="rule_version", target_code=rule_code, target_version=version)
    db.commit()
    db.refresh(row)
    return row


def transition_published_version(db: Session, rule_code: str, version: str, target: str, actor_user_id: int, reason: str | None = None) -> TrainingRuleVersion:
    row = get_version(db, rule_code, version)
    validate_lifecycle_transition(row.lifecycle_status, target)
    row.lifecycle_status = target
    if target == "retired":
        row.retired_at = datetime.utcnow()
    current = db.scalar(select(TrainingRule).where(TrainingRule.code == rule_code, TrainingRule.version == version))
    if current is not None and target in {"deprecated", "retired"}:
        current.lifecycle_status = target
        current.enabled = False
    _audit(db, actor_user_id=actor_user_id, action=target, target_type="rule_version", target_code=rule_code, target_version=version, reason=reason)
    db.commit()
    db.refresh(row)
    return row


def rollback_version(db: Session, rule_code: str, version: str, actor_user_id: int, reason: str) -> TrainingRuleVersion:
    if not reason:
        raise BadRequestError("Rollback reason is required.")
    target = get_version(db, rule_code, version)
    if target.lifecycle_status not in {"deprecated", "published"}:
        raise BadRequestError("Only deprecated or published versions can be rollback targets.")
    if target.lifecycle_status == "deprecated":
        target.lifecycle_status = "published"
    target.published_at = datetime.utcnow()
    for item in db.scalars(select(TrainingRuleVersion).where(TrainingRuleVersion.rule_code == rule_code, TrainingRuleVersion.id != target.id, TrainingRuleVersion.lifecycle_status == "published")):
        item.lifecycle_status = "deprecated"
    current = db.scalar(select(TrainingRule).where(TrainingRule.code == rule_code))
    if current is None:
        current = TrainingRule(code=rule_code)
        db.add(current)
    current.name = target.name
    current.description = target.description
    current.category = target.category
    current.scope = target.scope
    current.conditions_json = target.conditions_json
    current.result_json = target.result_json
    current.applicability_json = target.applicability_json
    current.thresholds_json = target.thresholds_json
    current.explanation_template = target.explanation_template
    current.severity = target.severity
    current.priority = target.priority
    current.version = target.version
    current.current_version = target.version
    current.current_version_id = target.id
    current.enabled = True
    current.public = True
    current.source_type = target.source_type
    current.lifecycle_status = "published"
    _audit(db, actor_user_id=actor_user_id, action="rollback", target_type="rule_version", target_code=rule_code, target_version=version, reason=reason)
    db.commit()
    db.refresh(target)
    return target


def list_test_cases(db: Session, context_type: str | None = None) -> list[TrainingRuleTestCase]:
    stmt = select(TrainingRuleTestCase)
    if context_type:
        stmt = stmt.where(TrainingRuleTestCase.context_type == context_type)
    return list(db.scalars(stmt.order_by(TrainingRuleTestCase.context_type, TrainingRuleTestCase.code)))


def create_test_case(db: Session, payload: Any, actor_user_id: int) -> TrainingRuleTestCase:
    if db.scalar(select(TrainingRuleTestCase).where(TrainingRuleTestCase.code == payload.code)):
        raise BadRequestError("Rule test case code already exists.")
    row = TrainingRuleTestCase(**payload.model_dump())
    db.add(row)
    _audit(db, actor_user_id=actor_user_id, action="create_test_case", target_type="rule_test_case", target_code=row.code, after=payload.model_dump())
    db.commit()
    db.refresh(row)
    return row


def get_test_case(db: Session, code: str) -> TrainingRuleTestCase:
    row = db.scalar(select(TrainingRuleTestCase).where(TrainingRuleTestCase.code == code))
    if row is None:
        raise NotFoundError("Rule test case not found.")
    return row


def update_test_case(db: Session, code: str, payload: Any, actor_user_id: int) -> TrainingRuleTestCase:
    row = get_test_case(db, code)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    _audit(db, actor_user_id=actor_user_id, action="update_test_case", target_type="rule_test_case", target_code=code, after=data)
    db.commit()
    db.refresh(row)
    return row


def run_tests(db: Session, request: RuleTestRunRequest, actor_user_id: int | None = None) -> TrainingRuleTestRun:
    cases_stmt = select(TrainingRuleTestCase).where(TrainingRuleTestCase.enabled.is_(True))
    if request.context_type:
        cases_stmt = cases_stmt.where(TrainingRuleTestCase.context_type == request.context_type)
    if request.tag:
        # MySQL JSON contains support varies by version; keep first pass in Python.
        pass
    cases = list(db.scalars(cases_stmt.order_by(TrainingRuleTestCase.context_type, TrainingRuleTestCase.code)))
    if request.tag:
        cases = [case for case in cases if request.tag in (case.tags_json or [])]
    run = TrainingRuleTestRun(ruleset_version=DEFAULT_RULESET_VERSION, run_type=request.run_type, status="running", created_by=actor_user_id)
    db.add(run)
    db.flush()
    engine = TrainingRuleEngine(ruleset_version=DEFAULT_RULESET_VERSION)
    rules = _published_rules(db)
    passed = 0
    failed = 0
    for case in cases:
        started = time.perf_counter()
        error_message = None
        try:
            result = engine.evaluate(case.facts_json, rules, case.context_type)
            diff = diff_results(case.expected_result_json, result)
            case_passed = not diff
            actual = result.model_dump(mode="json")
        except Exception as exc:  # defensive for admin test runner
            case_passed = False
            diff = {"error": str(exc)}
            actual = {}
            error_message = str(exc)
        duration_ms = int((time.perf_counter() - started) * 1000)
        passed += 1 if case_passed else 0
        failed += 0 if case_passed else 1
        db.add(
            TrainingRuleTestResult(
                test_run_id=run.id,
                test_case_code=case.code,
                passed=case_passed,
                actual_result_json=actual,
                expected_result_json=case.expected_result_json,
                diff_json=diff,
                duration_ms=duration_ms,
                error_message=error_message,
            )
        )
        if request.fail_fast and not case_passed:
            break
    run.total_cases = passed + failed
    run.passed_cases = passed
    run.failed_cases = failed
    run.status = "passed" if failed == 0 and run.total_cases > 0 else "failed"
    run.result_summary_json = {"passed": passed, "failed": failed, "total": run.total_cases}
    run.finished_at = datetime.utcnow()
    _audit(db, actor_user_id=actor_user_id, action="run_tests", target_type="rule_tests", after=run.result_summary_json)
    db.commit()
    db.refresh(run)
    return run


def list_test_runs(db: Session) -> list[TrainingRuleTestRun]:
    return list(db.scalars(select(TrainingRuleTestRun).order_by(TrainingRuleTestRun.started_at.desc(), TrainingRuleTestRun.id.desc()).limit(100)))


def get_test_run(db: Session, run_id: int) -> TrainingRuleTestRun:
    row = db.get(TrainingRuleTestRun, run_id)
    if row is None:
        raise NotFoundError("Rule test run not found.")
    return row


def list_test_results(db: Session, run_id: int) -> list[TrainingRuleTestResult]:
    get_test_run(db, run_id)
    return list(db.scalars(select(TrainingRuleTestResult).where(TrainingRuleTestResult.test_run_id == run_id).order_by(TrainingRuleTestResult.test_case_code)))


def coverage(db: Session) -> dict[str, Any]:
    rules = list(db.scalars(select(TrainingRule).where(TrainingRule.lifecycle_status == "published", TrainingRule.enabled.is_(True))))
    cases = list(db.scalars(select(TrainingRuleTestCase)))
    by_type: dict[str, set[str]] = {"positive": set(), "negative": set(), "boundary": set(), "conflict": set()}
    for case in cases:
        expected = case.expected_result_json or {}
        codes = set(expected.get("expected_rule_codes") or [])
        if case.source_type == "negative":
            codes.update(expected.get("unexpected_rule_codes") or [])
        if case.source_type in by_type:
            by_type[case.source_type].update(codes)
    rule_codes = {rule.code for rule in rules}
    covered = by_type["positive"] | by_type["negative"]
    by_scope: dict[str, dict[str, int]] = {}
    by_severity: dict[str, dict[str, int]] = {}
    for rule in rules:
        by_scope.setdefault(rule.scope, {"total": 0, "covered": 0})
        by_severity.setdefault(rule.severity, {"total": 0, "covered": 0})
        by_scope[rule.scope]["total"] += 1
        by_severity[rule.severity]["total"] += 1
        if rule.code in covered:
            by_scope[rule.scope]["covered"] += 1
            by_severity[rule.severity]["covered"] += 1
    return {
        "published_rules": len(rules),
        "rules_with_positive_case": len(rule_codes & by_type["positive"]),
        "rules_with_negative_case": len(rule_codes & by_type["negative"]),
        "rules_with_boundary_case": len(rule_codes & by_type["boundary"]),
        "rules_with_conflict_case": len(rule_codes & by_type["conflict"]),
        "uncovered_rules": sorted(rule_codes - covered),
        "by_scope": by_scope,
        "by_severity": by_severity,
    }


def metrics(db: Session) -> dict[str, Any]:
    rule_hits = {code: count for code, count in db.execute(select(TrainingRuleHit.rule_code, func.count()).group_by(TrainingRuleHit.rule_code)).all()}
    dominant_counts = {code: count for code, count in db.execute(select(TrainingRuleEvaluation.dominant_rule_code, func.count()).where(TrainingRuleEvaluation.dominant_rule_code.is_not(None)).group_by(TrainingRuleEvaluation.dominant_rule_code)).all()}
    action_distribution: dict[str, int] = {}
    severity_distribution = {severity: count for severity, count in db.execute(select(TrainingRuleHit.severity, func.count()).group_by(TrainingRuleHit.severity)).all()}
    context_distribution = {context: count for context, count in db.execute(select(TrainingRuleEvaluation.context_type, func.count()).group_by(TrainingRuleEvaluation.context_type)).all()}
    status_counts: dict[str, int] = {}
    for row in db.scalars(select(TrainingRuleEvaluation.final_result_json)):
        action = row.get("final_action") if isinstance(row, dict) else None
        if action:
            action_distribution[action] = action_distribution.get(action, 0) + 1
        for key, value in (row.get("rule_status_counts") or {}).items() if isinstance(row, dict) else []:
            status_counts[key] = status_counts.get(key, 0) + int(value)
    return {
        "rule_hits": rule_hits,
        "dominant_counts": dominant_counts,
        "action_distribution": action_distribution,
        "severity_distribution": severity_distribution,
        "context_distribution": context_distribution,
        "status_counts": status_counts,
    }


def impact_analysis(db: Session, rule_code: str, from_version: str, to_version: str) -> ImpactAnalysisRead:
    before = get_version(db, rule_code, from_version)
    after = get_version(db, rule_code, to_version)
    field_changes = {}
    for field in ["conditions_json", "result_json", "applicability_json", "thresholds_json", "severity", "priority", "explanation_template"]:
        old = getattr(before, field)
        new = getattr(after, field)
        if old != new:
            field_changes[field] = {"from": old, "to": new}
    threshold_changes = []
    before_thresholds = {item.get("key"): item for item in before.thresholds_json or []}
    after_thresholds = {item.get("key"): item for item in after.thresholds_json or []}
    for key in sorted(set(before_thresholds) | set(after_thresholds)):
        if before_thresholds.get(key) != after_thresholds.get(key):
            threshold_changes.append({"key": key, "from": before_thresholds.get(key), "to": after_thresholds.get(key)})
    cases = list(db.scalars(select(TrainingRuleTestCase).where(TrainingRuleTestCase.enabled.is_(True)).order_by(TrainingRuleTestCase.code)))
    published_rules = [rule for rule in _published_rules(db) if rule.code != rule_code]
    engine = TrainingRuleEngine()
    old_rule = _version_to_definition(before).model_copy(update={"lifecycle_status": RuleLifecycleStatus.published})
    new_rule = _version_to_definition(after).model_copy(update={"lifecycle_status": RuleLifecycleStatus.published})
    behavior = {"matched_to_unmatched": 0, "unmatched_to_matched": 0, "final_action_changed": 0, "dominant_rule_changed": 0}
    for case in cases:
        old_result = engine.evaluate(case.facts_json, [*published_rules, old_rule], case.context_type)
        new_result = engine.evaluate(case.facts_json, [*published_rules, new_rule], case.context_type)
        old_matched = rule_code in old_result.matched_rule_codes
        new_matched = rule_code in new_result.matched_rule_codes
        if old_matched and not new_matched:
            behavior["matched_to_unmatched"] += 1
        if new_matched and not old_matched:
            behavior["unmatched_to_matched"] += 1
        if old_result.final_action != new_result.final_action:
            behavior["final_action_changed"] += 1
        if old_result.dominant_rule_code != new_result.dominant_rule_code:
            behavior["dominant_rule_changed"] += 1
    return ImpactAnalysisRead(
        rule_code=rule_code,
        from_version=from_version,
        to_version=to_version,
        field_changes=field_changes,
        behavior_changes=behavior,
        threshold_changes=threshold_changes,
    )
