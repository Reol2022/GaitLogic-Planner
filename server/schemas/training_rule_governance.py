from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

DOI_PREFIX = "10."
EVIDENCE_SOURCE_TYPES = {
    "peer_reviewed_article",
    "systematic_review",
    "meta_analysis",
    "consensus_statement",
    "textbook",
    "official_guideline",
    "public_dataset",
    "product_rule",
    "expert_practice",
    "system_default",
    "safety_boundary",
}
EVIDENCE_LEVELS = {"high", "moderate", "limited", "expert_consensus", "product_assumption", "not_applicable"}
EVIDENCE_REVIEW_STATUSES = {"draft", "verified", "needs_review", "deprecated", "archived"}
RELATIONSHIP_TYPES = {
    "supports_concept",
    "supports_threshold",
    "supports_direction",
    "supports_safety_boundary",
    "background_reference",
    "product_interpretation",
}
RULE_LIFECYCLE_STATUSES = {"draft", "in_review", "approved", "published", "deprecated", "retired", "rejected"}
REVIEW_STATUSES = {"pending", "changes_requested", "approved", "rejected"}
TEST_CASE_TYPES = {"positive", "negative", "boundary", "conflict", "missing_data", "not_applicable", "regression"}


class EvidenceSourceBase(BaseModel):
    code: str = Field(max_length=96)
    title: str = Field(max_length=255)
    authors: str | None = None
    publication_year: int | None = None
    source_type: str
    publication_name: str | None = None
    doi: str | None = None
    url: str | None = None
    language: str | None = None
    summary: str
    evidence_level: str
    review_status: str = "draft"
    copyright_note: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        if value not in EVIDENCE_SOURCE_TYPES:
            raise ValueError("Unsupported evidence source_type.")
        return value

    @field_validator("evidence_level")
    @classmethod
    def validate_evidence_level(cls, value: str) -> str:
        if value not in EVIDENCE_LEVELS:
            raise ValueError("Unsupported evidence_level.")
        return value

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, value: str) -> str:
        if value not in EVIDENCE_REVIEW_STATUSES:
            raise ValueError("Unsupported review_status.")
        return value

    @field_validator("doi")
    @classmethod
    def validate_doi(cls, value: str | None) -> str | None:
        if value and not value.startswith(DOI_PREFIX):
            raise ValueError("DOI should start with 10.")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("URL must start with http:// or https://.")
        return value


class EvidenceSourceCreate(EvidenceSourceBase):
    pass


class EvidenceSourceUpdate(BaseModel):
    title: str | None = None
    authors: str | None = None
    publication_year: int | None = None
    source_type: str | None = None
    publication_name: str | None = None
    doi: str | None = None
    url: str | None = None
    language: str | None = None
    summary: str | None = None
    evidence_level: str | None = None
    review_status: str | None = None
    copyright_note: str | None = None
    metadata_json: dict[str, Any] | None = None


class EvidenceSourceRead(EvidenceSourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidencePublicRead(BaseModel):
    code: str
    title: str
    source_type: str
    publication_year: int | None = None
    publication_name: str | None = None
    doi: str | None = None
    url: str | None = None
    summary: str
    evidence_level: str
    review_status: str

    model_config = ConfigDict(from_attributes=True)


class RuleEvidenceLinkRead(BaseModel):
    id: int
    rule_code: str
    rule_version: str
    evidence_source_code: str
    relationship_type: str
    support_note: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleVersionCreate(BaseModel):
    version: str
    name: str
    description: str | None = None
    category: str
    scope: str
    conditions_json: dict[str, Any]
    result_json: dict[str, Any]
    applicability_json: dict[str, Any] = Field(default_factory=dict)
    thresholds_json: list[dict[str, Any]] = Field(default_factory=list)
    explanation_template: str
    severity: str = "info"
    priority: int = 0
    source_type: str = "product_rule"
    change_summary: str | None = None
    evidence_links: list[dict[str, Any]] = Field(default_factory=list)


class RuleVersionRead(BaseModel):
    id: int
    rule_code: str
    version: str
    name: str
    description: str | None = None
    category: str
    scope: str
    conditions_json: dict[str, Any]
    result_json: dict[str, Any]
    applicability_json: dict[str, Any]
    thresholds_json: list[dict[str, Any]]
    explanation_template: str
    severity: str
    priority: int
    source_type: str
    lifecycle_status: str
    content_hash: str
    change_summary: str | None = None
    created_by: int | None = None
    created_at: datetime
    published_at: datetime | None = None
    retired_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ReviewRead(BaseModel):
    id: int
    rule_code: str
    rule_version: str
    reviewer_id: int | None = None
    review_status: str
    review_comment: str | None = None
    checklist_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewActionRequest(BaseModel):
    comment: str | None = None
    checklist_json: dict[str, Any] = Field(default_factory=dict)


class RuleTestCaseCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    context_type: str
    facts_json: dict[str, Any]
    expected_result_json: dict[str, Any]
    tags_json: list[str] = Field(default_factory=list)
    source_type: str = "positive"
    enabled: bool = True

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        if value not in TEST_CASE_TYPES:
            raise ValueError("Unsupported test case source_type.")
        return value


class RuleTestCaseRead(RuleTestCaseCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleTestRunRequest(BaseModel):
    run_type: str = "manual"
    scope: str | None = None
    rule_code: str | None = None
    context_type: str | None = None
    tag: str | None = None
    fail_fast: bool = False


class RuleTestResultRead(BaseModel):
    id: int
    test_run_id: int
    test_case_code: str
    passed: bool
    actual_result_json: dict[str, Any]
    expected_result_json: dict[str, Any]
    diff_json: dict[str, Any]
    duration_ms: int
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RuleTestRunRead(BaseModel):
    id: int
    ruleset_version: str
    run_type: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    result_summary_json: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None = None
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CoverageRead(BaseModel):
    published_rules: int
    rules_with_positive_case: int
    rules_with_negative_case: int
    rules_with_boundary_case: int
    rules_with_conflict_case: int
    uncovered_rules: list[str]
    by_scope: dict[str, dict[str, int]]
    by_severity: dict[str, dict[str, int]]


class MetricsRead(BaseModel):
    rule_hits: dict[str, int]
    dominant_counts: dict[str, int]
    action_distribution: dict[str, int]
    severity_distribution: dict[str, int]
    context_distribution: dict[str, int]
    status_counts: dict[str, int]


class ImpactAnalysisRequest(BaseModel):
    rule_code: str
    from_version: str
    to_version: str


class ImpactAnalysisRead(BaseModel):
    rule_code: str
    from_version: str
    to_version: str
    field_changes: dict[str, Any]
    behavior_changes: dict[str, int]
    threshold_changes: list[dict[str, Any]]


class PackageValidationRead(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)
