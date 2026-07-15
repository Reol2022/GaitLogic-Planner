from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from planner_core.training_knowledge.enums import CONTEXT_TYPES
from planner_core.training_knowledge.schemas import EngineEvaluationResult, TrainingRuleDefinition
from planner_core.training_knowledge.validators import validate_rule_definition

MAX_FACTS_JSON_CHARS = 65536
MAX_FACTS_DEPTH = 16


def _json_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, dict):
        if not value:
            return depth + 1
        return max(_json_depth(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return depth + 1
        return max(_json_depth(item, depth + 1) for item in value)
    return depth


class TrainingRuleRead(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    category: str
    scope: str
    severity: str
    priority: int
    evidence_refs_json: list[str] = Field(default_factory=list)
    version: str
    enabled: bool
    public: bool
    source_type: str
    lifecycle_status: str = "published"
    current_version: str | None = None
    applicability_json: dict[str, Any] = Field(default_factory=dict)
    thresholds_json: list[dict[str, Any]] = Field(default_factory=list)
    conditions_json: dict[str, Any] | None = None
    result_json: dict[str, Any] | None = None
    explanation_template: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingRulesResponse(BaseModel):
    items: list[TrainingRuleRead]
    total: int
    limit: int
    offset: int


class TrainingRuleEnabledUpdate(BaseModel):
    enabled: bool


class TrainingRuleValidateRequest(BaseModel):
    definition: dict[str, Any]

    @model_validator(mode="after")
    def validate_definition(self) -> TrainingRuleValidateRequest:
        validate_rule_definition(self.definition)
        return self


class TrainingRuleValidateResponse(BaseModel):
    valid: bool
    rule: TrainingRuleDefinition | None = None


class TrainingRuleSyncResponse(BaseModel):
    added_items: int
    updated_items: int
    skipped_items: int
    added_rules: int
    updated_rules: int
    skipped_rules: int


class TrainingRuleEvaluateRequest(BaseModel):
    context_type: str = Field(default="generic")
    context_id: str | None = Field(default=None, max_length=128)
    facts: dict[str, Any]
    persist: bool = True

    @field_validator("context_type")
    @classmethod
    def validate_context_type(cls, value: str) -> str:
        if value not in CONTEXT_TYPES:
            raise ValueError("Unsupported context_type.")
        return value

    @field_validator("facts")
    @classmethod
    def validate_facts_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        size = len(json.dumps(value, ensure_ascii=False))
        if size > MAX_FACTS_JSON_CHARS:
            raise ValueError("facts JSON exceeds size limit.")
        if _json_depth(value) > MAX_FACTS_DEPTH:
            raise ValueError("facts JSON exceeds depth limit.")
        return value


class TrainingRuleMatchedRead(BaseModel):
    rule_code: str
    rule_version: str
    severity: str
    priority: int
    action: str
    recommendation: str | None = None
    explanation: str
    output: dict[str, Any] = Field(default_factory=dict)


class TrainingRuleEvaluateResponse(BaseModel):
    evaluation_id: int | None = None
    context_type: str
    final_action: str
    dominant_rule_code: str | None = None
    matched_rules: list[TrainingRuleMatchedRead] = Field(default_factory=list)
    conflict_resolution: dict[str, Any]
    recommendations: list[str] = Field(default_factory=list)
    rule_status_counts: dict[str, int] = Field(default_factory=dict)
    rule_traces: list[dict[str, Any]] = Field(default_factory=list)
    engine_version: str
    ruleset_version: str

    @classmethod
    def from_engine_result(
        cls,
        result: EngineEvaluationResult,
        evaluation_id: int | None = None,
    ) -> TrainingRuleEvaluateResponse:
        return cls(
            evaluation_id=evaluation_id,
            context_type=result.context_type,
            final_action=result.final_action,
            dominant_rule_code=result.dominant_rule_code,
            matched_rules=[
                TrainingRuleMatchedRead(
                    rule_code=hit.rule_code,
                    rule_version=hit.rule_version,
                    severity=hit.severity,
                    priority=hit.priority,
                    action=hit.action,
                    recommendation=hit.recommendation,
                    explanation=hit.explanation,
                    output=hit.output,
                )
                for hit in result.matched_rules
            ],
            conflict_resolution=result.conflict_resolution.model_dump(mode="json"),
            recommendations=result.recommendations,
            rule_status_counts=result.rule_status_counts,
            rule_traces=[trace.model_dump(mode="json") for trace in result.rule_traces],
            engine_version=result.engine_version,
            ruleset_version=result.ruleset_version,
        )


class TrainingRuleEvaluationRead(BaseModel):
    id: int
    user_id: int
    context_type: str
    context_id: str | None = None
    input_snapshot_json: dict[str, Any]
    final_result_json: dict[str, Any]
    dominant_rule_code: str | None = None
    engine_version: str
    ruleset_version: str
    facts_hash: str | None = None
    source_version: str | None = None
    is_stale: bool = False
    stale_reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingRuleHitRead(BaseModel):
    id: int
    evaluation_id: int
    rule_code: str
    rule_version: str
    matched: bool
    severity: str
    priority: int
    output_json: dict[str, Any]
    explanation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingRuleEvaluationDetail(TrainingRuleEvaluationRead):
    hits: list[TrainingRuleHitRead] = Field(default_factory=list)


class TrainingRuleEvaluationsResponse(BaseModel):
    items: list[TrainingRuleEvaluationRead]
    total: int
    limit: int
    offset: int
