from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from planner_core.training_knowledge.enums import (
    ConditionOperator,
    EvidenceLevel,
    KnowledgeStatus,
    RuleEvaluationStatus,
    RuleLifecycleStatus,
    RuleAction,
    RuleSeverity,
    RuleSourceType,
)

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
FIELD_PATH_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
BLOCKED_FIELD_SEGMENTS = {"__class__", "__dict__", "__mro__", "__subclasses__", "func_globals"}


class ConditionLeaf(BaseModel):
    field: str
    operator: ConditionOperator
    value: Any = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        if not FIELD_PATH_PATTERN.match(value):
            raise ValueError("Field path must use dotted dictionary keys only.")
        segments = value.split(".")
        if any(segment.startswith("_") or segment in BLOCKED_FIELD_SEGMENTS for segment in segments):
            raise ValueError("Field path contains a blocked segment.")
        return value

    @model_validator(mode="after")
    def validate_operator_value(self) -> ConditionLeaf:
        operator = self.operator.value
        if operator == "between":
            if not isinstance(self.value, dict):
                raise ValueError("between value must be an object.")
            if "min" not in self.value or "max" not in self.value:
                raise ValueError("between value must include min and max.")
        if operator in {"in", "not_in"} and not isinstance(self.value, list):
            raise ValueError("in and not_in values must be arrays.")
        return self


class ConditionNode(BaseModel):
    all: list[Any] | None = None
    any: list[Any] | None = None
    not_: Any | None = Field(default=None, alias="not")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_single_operator(self) -> ConditionNode:
        count = sum(value is not None for value in (self.all, self.any, self.not_))
        if count != 1:
            raise ValueError("Condition node must contain exactly one of all, any, or not.")
        if self.all is not None and not self.all:
            raise ValueError("all cannot be empty.")
        if self.any is not None and not self.any:
            raise ValueError("any cannot be empty.")
        return self


class RuleResultDefinition(BaseModel):
    action: RuleAction
    recommendation: str | None = None
    message_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgeScopeDefinition(BaseModel):
    min: int | None = None
    max: int | None = None


class ApplicabilityDefinition(BaseModel):
    sports: list[str] = Field(default_factory=lambda: ["running"])
    race_distances: list[str] = Field(default_factory=list)
    training_phases: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(default_factory=list)
    age_scope: AgeScopeDefinition = Field(default_factory=AgeScopeDefinition)
    requires_fields: list[str] = Field(default_factory=list)
    excluded_conditions: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("requires_fields")
    @classmethod
    def validate_required_fields(cls, value: list[str]) -> list[str]:
        for path in value:
            if not FIELD_PATH_PATTERN.match(path):
                raise ValueError(f"Unsafe required field path: {path}")
        return value


class ThresholdDefinition(BaseModel):
    key: str
    value: int | float | str
    unit: str
    source_type: RuleSourceType = RuleSourceType.product_rule
    evidence_source_codes: list[str] = Field(default_factory=list)
    configurable: bool = False
    description: str


class TrainingKnowledgeItemDefinition(BaseModel):
    code: str
    name: str
    english_name: str | None = None
    category: str
    definition: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    related_codes: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    evidence_level: EvidenceLevel = EvidenceLevel.product_rule
    version: str = "1.0.0"
    status: KnowledgeStatus = KnowledgeStatus.active

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not CODE_PATTERN.match(value):
            raise ValueError("code must be stable uppercase snake case.")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_PATTERN.match(value):
            raise ValueError("version must use semantic version format.")
        return value


class TrainingRuleDefinition(BaseModel):
    code: str
    name: str
    description: str | None = None
    category: str
    scope: str = "generic"
    conditions: dict[str, Any]
    result: RuleResultDefinition
    explanation_template: str
    severity: RuleSeverity = RuleSeverity.info
    priority: int = 0
    evidence_refs: list[str] = Field(default_factory=list)
    applicability: ApplicabilityDefinition = Field(default_factory=ApplicabilityDefinition)
    thresholds: list[ThresholdDefinition] = Field(default_factory=list)
    version: str = "1.0.0"
    enabled: bool = True
    public: bool = True
    source_type: RuleSourceType = RuleSourceType.product_rule
    lifecycle_status: RuleLifecycleStatus = RuleLifecycleStatus.published

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not CODE_PATTERN.match(value):
            raise ValueError("code must be stable uppercase snake case.")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_PATTERN.match(value):
            raise ValueError("version must use semantic version format.")
        return value

    @field_validator("explanation_template")
    @classmethod
    def validate_template_length(cls, value: str) -> str:
        if len(value) > 1000:
            raise ValueError("explanation_template is too long.")
        return value


class ConditionEvaluation(BaseModel):
    matched: bool
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    status: RuleEvaluationStatus = RuleEvaluationStatus.not_matched


class RuleHit(BaseModel):
    rule_code: str
    rule_version: str
    matched: bool
    severity: str
    priority: int
    action: str
    recommendation: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    explanation: str
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ConflictResolution(BaseModel):
    strategy: Literal["highest_severity_then_priority"] = "highest_severity_then_priority"
    reason: str = "safety_priority"
    action_order: str = "product_policy_v1"
    conflict_types: list[str] = Field(default_factory=list)
    conflict_requires_manual_review: bool = False


class RuleEvaluationTrace(BaseModel):
    rule_code: str
    rule_version: str
    status: RuleEvaluationStatus
    reason: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class EngineEvaluationResult(BaseModel):
    context_type: str
    final_action: str
    dominant_rule_code: str | None = None
    matched_rule_codes: list[str] = Field(default_factory=list)
    matched_rules: list[RuleHit] = Field(default_factory=list)
    conflict_resolution: ConflictResolution = Field(default_factory=ConflictResolution)
    recommendations: list[str] = Field(default_factory=list)
    rule_status_counts: dict[str, int] = Field(default_factory=dict)
    rule_traces: list[RuleEvaluationTrace] = Field(default_factory=list)
    engine_version: str
    ruleset_version: str
