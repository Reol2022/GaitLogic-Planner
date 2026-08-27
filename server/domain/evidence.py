from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.domain.decision_readiness import DomainReadiness


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceKind(str, Enum):
    PERSONAL_FACT = "PERSONAL_FACT"
    DERIVED_FACT = "DERIVED_FACT"
    RULE_DECISION = "RULE_DECISION"
    KNOWLEDGE_EVIDENCE = "KNOWLEDGE_EVIDENCE"
    CAPABILITY_INFORMATION = "CAPABILITY_INFORMATION"


class EvidenceSourceKind(str, Enum):
    TRAINING_PLAN = "TRAINING_PLAN"
    TRAINING_LOG = "TRAINING_LOG"
    RUNNER_STATE = "RUNNER_STATE"
    GARMIN_NORMALIZED = "GARMIN_NORMALIZED"
    USER_INPUT = "USER_INPUT"
    DERIVED_METRIC = "DERIVED_METRIC"
    RULE_ENGINE = "RULE_ENGINE"
    KNOWLEDGE_CORPUS = "KNOWLEDGE_CORPUS"
    SYSTEM_CAPABILITY = "SYSTEM_CAPABILITY"
    WEEKLY_FACTS = "WEEKLY_FACTS"


class EvidenceFreshness(str, Enum):
    CURRENT = "CURRENT"
    RECENT = "RECENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class EvidenceCoverage(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class EvidenceUsability(str, Enum):
    USABLE = "USABLE"
    LIMITED = "LIMITED"
    UNUSABLE = "UNUSABLE"


class EvidenceAssessmentStatus(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    CONFLICTED = "CONFLICTED"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceProvenance(EvidenceModel):
    canonical_fact_identity: str = Field(min_length=1, max_length=240)
    source_record_refs: list[str] = Field(default_factory=list, max_length=50)
    derived_from: list[str] = Field(default_factory=list, max_length=50)
    provider: str | None = Field(default=None, max_length=80)


class EvidenceItem(EvidenceModel):
    evidence_id: str = Field(min_length=1, max_length=80)
    evidence_kind: EvidenceKind
    source_kind: EvidenceSourceKind
    source_ref: str = Field(min_length=1, max_length=240)
    domain: str = Field(min_length=1, max_length=80)
    fact_key: str = Field(min_length=1, max_length=120)
    semantic_key: str | None = Field(default=None, max_length=120)
    semantic_value: str | None = Field(default=None, max_length=120)
    observed_at: date | datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    freshness: EvidenceFreshness = EvidenceFreshness.UNKNOWN
    coverage: EvidenceCoverage = EvidenceCoverage.UNKNOWN
    usability: EvidenceUsability = EvidenceUsability.USABLE
    limitation_codes: list[str] = Field(default_factory=list, max_length=30)
    provenance: EvidenceProvenance


class EvidenceRequirement(EvidenceModel):
    fact_keys: list[str] = Field(min_length=1, max_length=12)
    accepted_kinds: list[EvidenceKind] = Field(min_length=1, max_length=5)
    candidate_tools: list[str] = Field(default_factory=list, max_length=8)
    description: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def unique_values(self) -> "EvidenceRequirement":
        if len(self.fact_keys) != len(set(self.fact_keys)):
            raise ValueError("fact_keys must be unique")
        if len(self.candidate_tools) != len(set(self.candidate_tools)):
            raise ValueError("candidate_tools must be unique")
        return self


class RequiredEvidenceProfile(EvidenceModel):
    domain: str = Field(min_length=1, max_length=80)
    required: list[EvidenceRequirement] = Field(default_factory=list, max_length=12)
    optional_fact_keys: list[str] = Field(default_factory=list, max_length=20)


class MissingEvidence(EvidenceModel):
    fact_keys: list[str] = Field(min_length=1, max_length=12)
    description: str = Field(min_length=1, max_length=240)
    candidate_tools: list[str] = Field(default_factory=list, max_length=8)
    automatically_resolvable: bool


class EvidenceConflict(EvidenceModel):
    code: str = Field(min_length=1, max_length=120)
    domain: str = Field(min_length=1, max_length=80)
    semantic_key: str = Field(min_length=1, max_length=120)
    evidence_ids: list[str] = Field(min_length=2, max_length=12)
    source_kinds: list[EvidenceSourceKind] = Field(min_length=2, max_length=12)


class EvidenceAssessment(EvidenceModel):
    domain: str = Field(min_length=1, max_length=80)
    status: EvidenceAssessmentStatus
    usable_evidence: list[str] = Field(default_factory=list, max_length=80)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list, max_length=20)
    conflicts: list[EvidenceConflict] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    source_summary: dict[str, int] = Field(default_factory=dict)


class EvidenceJudgeResult(EvidenceModel):
    relevant_domains: list[str] = Field(default_factory=list, max_length=30)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=200)
    assessments: list[EvidenceAssessment] = Field(default_factory=list, max_length=30)
    decision_readiness: list[DomainReadiness] = Field(default_factory=list, max_length=30)
    evidence_fingerprint: str = Field(min_length=64, max_length=64)


class ReflectAction(EvidenceModel):
    target_domain: str = Field(min_length=1, max_length=80)
    missing_fact: str = Field(min_length=1, max_length=120)
    tool_name: str | None = Field(default=None, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=300)
    priority: int = Field(ge=1, le=100)
    automatically_resolvable: bool
    already_attempted: bool = False
    fingerprint: str | None = Field(default=None, min_length=64, max_length=64)


class MissingEvidencePlan(EvidenceModel):
    actions: list[ReflectAction] = Field(default_factory=list, max_length=20)
    stop_reasons: list[str] = Field(default_factory=list, max_length=20)


class ReflectSummary(EvidenceModel):
    rounds: int = Field(default=0, ge=0, le=2)
    triggered: bool = False
    executed_action_count: int = Field(default=0, ge=0, le=20)
    evidence_added_count: int = Field(default=0, ge=0, le=200)
    no_marginal_gain: bool = False
    max_rounds_reached: bool = False
    stop_reasons: list[str] = Field(default_factory=list, max_length=20)
