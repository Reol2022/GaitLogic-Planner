from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db, require_admin_user
from server.schemas.training_rule_governance import (
    CoverageRead,
    EvidencePublicRead,
    EvidenceSourceCreate,
    EvidenceSourceRead,
    EvidenceSourceUpdate,
    ImpactAnalysisRead,
    ImpactAnalysisRequest,
    MetricsRead,
    PackageValidationRead,
    ReviewActionRequest,
    ReviewRead,
    RuleTestCaseCreate,
    RuleTestCaseRead,
    RuleTestResultRead,
    RuleTestRunRead,
    RuleTestRunRequest,
    RuleVersionCreate,
    RuleVersionRead,
)
from server.services import training_rule_governance_service as governance

router = APIRouter(tags=["training rule governance"])


@router.get("/training-evidence/public/{code}", response_model=EvidencePublicRead)
def get_public_evidence(
    code: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return governance.get_evidence(db, code, public=True)


@router.get("/admin/training-evidence", response_model=list[EvidenceSourceRead])
def list_evidence(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.list_evidence(db)


@router.post("/admin/training-evidence", response_model=EvidenceSourceRead)
def create_evidence(
    payload: EvidenceSourceCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.create_evidence(db, payload, current_user.id)


@router.get("/admin/training-evidence/{code}", response_model=EvidenceSourceRead)
def get_evidence(
    code: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.get_evidence(db, code)


@router.patch("/admin/training-evidence/{code}", response_model=EvidenceSourceRead)
def update_evidence(
    code: str,
    payload: EvidenceSourceUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.update_evidence(db, code, payload, current_user.id)


@router.post("/admin/training-evidence/{code}/archive", response_model=EvidenceSourceRead)
def archive_evidence(
    code: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.archive_evidence(db, code, current_user.id)


@router.get("/admin/training-rules/{code}/versions", response_model=list[RuleVersionRead])
def list_versions(
    code: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.list_versions(db, code)


@router.get("/admin/training-rules/{code}/versions/{version}", response_model=RuleVersionRead)
def get_version(
    code: str,
    version: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.get_version(db, code, version)


@router.post("/admin/training-rules/{code}/versions", response_model=RuleVersionRead)
def create_version(
    code: str,
    payload: RuleVersionCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.create_version(db, code, payload, current_user.id)


@router.post("/admin/training-rules/{code}/versions/{version}/submit-review", response_model=RuleVersionRead)
def submit_review(
    code: str,
    version: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.submit_review(db, code, version, current_user.id)


@router.get("/admin/training-rule-reviews", response_model=list[ReviewRead])
def list_reviews(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.list_reviews(db)


@router.get("/admin/training-rule-reviews/{review_id}", response_model=ReviewRead)
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.get_review(db, review_id)


@router.post("/admin/training-rule-reviews/{review_id}/request-changes", response_model=ReviewRead)
def request_changes(
    review_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.review_action(db, review_id, current_user.id, "changes_requested", payload.comment, payload.checklist_json)


@router.post("/admin/training-rule-reviews/{review_id}/approve", response_model=ReviewRead)
def approve_review(
    review_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.review_action(db, review_id, current_user.id, "approved", payload.comment, payload.checklist_json)


@router.post("/admin/training-rule-reviews/{review_id}/reject", response_model=ReviewRead)
def reject_review(
    review_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.review_action(db, review_id, current_user.id, "rejected", payload.comment, payload.checklist_json)


@router.post("/admin/training-rules/{code}/versions/{version}/publish", response_model=RuleVersionRead)
def publish_version(
    code: str,
    version: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.publish_version(db, code, version, current_user.id)


@router.post("/admin/training-rules/{code}/versions/{version}/deprecate", response_model=RuleVersionRead)
def deprecate_version(
    code: str,
    version: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.transition_published_version(db, code, version, "deprecated", current_user.id)


@router.post("/admin/training-rules/{code}/versions/{version}/retire", response_model=RuleVersionRead)
def retire_version(
    code: str,
    version: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.transition_published_version(db, code, version, "retired", current_user.id)


@router.post("/admin/training-rules/{code}/versions/{version}/rollback", response_model=RuleVersionRead)
def rollback_version(
    code: str,
    version: str,
    reason: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.rollback_version(db, code, version, current_user.id, reason)


@router.get("/admin/training-rule-test-cases", response_model=list[RuleTestCaseRead])
def list_test_cases(
    context_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.list_test_cases(db, context_type)


@router.post("/admin/training-rule-test-cases", response_model=RuleTestCaseRead)
def create_test_case(
    payload: RuleTestCaseCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.create_test_case(db, payload, current_user.id)


@router.get("/admin/training-rule-test-cases/{code}", response_model=RuleTestCaseRead)
def get_test_case(
    code: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.get_test_case(db, code)


@router.patch("/admin/training-rule-test-cases/{code}", response_model=RuleTestCaseRead)
def update_test_case(
    code: str,
    payload: RuleTestCaseCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.update_test_case(db, code, payload, current_user.id)


@router.post("/admin/training-rule-tests/run", response_model=RuleTestRunRead)
def run_tests(
    payload: RuleTestRunRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.run_tests(db, payload, current_user.id)


@router.get("/admin/training-rule-tests/runs", response_model=list[RuleTestRunRead])
def list_test_runs(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.list_test_runs(db)


@router.get("/admin/training-rule-tests/runs/{run_id}", response_model=RuleTestRunRead)
def get_test_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.get_test_run(db, run_id)


@router.get("/admin/training-rule-tests/runs/{run_id}/results", response_model=list[RuleTestResultRead])
def list_test_results(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.list_test_results(db, run_id)


@router.get("/admin/training-rules/coverage", response_model=CoverageRead)
def coverage(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.coverage(db)


@router.get("/admin/training-rules/metrics", response_model=MetricsRead)
def metrics(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.metrics(db)


@router.post("/admin/training-rules/impact-analysis", response_model=ImpactAnalysisRead)
def impact_analysis(
    payload: ImpactAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return governance.impact_analysis(db, payload.rule_code, payload.from_version, payload.to_version)


@router.get("/admin/training-rules/conflicts")
def conflicts(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    rows = []
    from planner_core.database.models import TrainingRuleEvaluation
    from sqlalchemy import select

    for item in db.scalars(select(TrainingRuleEvaluation).order_by(TrainingRuleEvaluation.created_at.desc()).limit(limit)):
        final = item.final_result_json or {}
        conflict = final.get("conflict_resolution") or {}
        if conflict.get("conflict_types"):
            rows.append({"evaluation_id": item.id, "context_type": item.context_type, "dominant_rule_code": item.dominant_rule_code, "conflict_resolution": conflict})
    return {"items": rows}


@router.post("/admin/training-rule-packages/validate", response_model=PackageValidationRead)
def validate_package(
    manifest: dict,
    current_user: UserAccount = Depends(require_admin_user),
):
    required = {"package_code", "package_name", "package_version", "engine_min_version", "facts_schema_version"}
    missing = sorted(required - set(manifest))
    return PackageValidationRead(valid=not missing, errors=[f"Missing manifest field: {item}" for item in missing], manifest=manifest)


@router.post("/admin/training-rule-packages/import", response_model=PackageValidationRead)
def import_package(
    manifest: dict,
    current_user: UserAccount = Depends(require_admin_user),
):
    result = validate_package(manifest, current_user)
    if not result.valid:
        return result
    return PackageValidationRead(valid=True, manifest=manifest)


@router.get("/admin/training-rule-packages/export")
def export_package(
    current_user: UserAccount = Depends(require_admin_user),
):
    return {
        "package_code": "GAITLOGIC_CORE_RULES",
        "package_name": "GaitLogic Core Rules",
        "package_version": "1.0.0",
        "engine_min_version": "1.0.0",
        "facts_schema_version": "1.0.0",
    }
