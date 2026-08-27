from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from server.domain.decision_readiness import DecisionReadiness


class AblationModel(BaseModel):
    """Strict public-evaluation contract; unknown fields are always rejected."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AblationVariant(str, Enum):
    A_LLM_ONLY = "A_LLM_ONLY"
    B_TOOLS_LLM = "B_TOOLS_LLM"
    C_TRUSTED_CORE = "C_TRUSTED_CORE"
    D_PARTIAL_FACTS = "D_PARTIAL_FACTS"
    E_EVIDENCE_JUDGE = "E_EVIDENCE_JUDGE"
    F_FULL_GAITLOGIC = "F_FULL_GAITLOGIC"
    G_FULL_WITHOUT_VALIDATOR = "G_FULL_WITHOUT_VALIDATOR"


class AblationCategory(str, Enum):
    FACT_QUERY = "FACT_QUERY"
    TRAINING_DECISION = "TRAINING_DECISION"
    PARTIAL_FACTS = "PARTIAL_FACTS"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    REFLECT = "REFLECT"
    UNRESOLVABLE_EVIDENCE = "UNRESOLVABLE_EVIDENCE"
    WEEKLY_REVIEW = "WEEKLY_REVIEW"
    PROPOSAL_SAFETY = "PROPOSAL_SAFETY"


class AblationConfig(AblationModel):
    """Evaluation-only architecture switches.

    The type is deliberately absent from settings, API schemas and production
    constructors, so no request or environment variable can weaken production.
    """

    variant: AblationVariant
    tools_enabled: bool
    rules_enabled: bool
    rag_enabled: bool
    validator_enabled: bool
    decision_readiness_enabled: bool
    evidence_judge_enabled: bool
    reflect_enabled: bool


class FactAssertion(AblationModel):
    fact_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    value: JsonValue


class ExpectedDomain(AblationModel):
    domain: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    readiness: DecisionReadiness
    expected_decision: str | None = Field(default=None, max_length=120)


class ExpectedToolBehavior(AblationModel):
    initial_tools: list[str] = Field(default_factory=list, max_length=12)
    reflect_tools: list[str] = Field(default_factory=list, max_length=6)
    forbidden_tools: list[str] = Field(default_factory=list, max_length=12)


class ExpectedReflectBehavior(AblationModel):
    should_trigger: bool = False
    resolvable: bool = False
    expected_resolution_domains: list[str] = Field(default_factory=list, max_length=8)


class CompetitionAblationCase(AblationModel):
    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    category: AblationCategory
    title: str = Field(min_length=1, max_length=180)
    user_query: str = Field(min_length=1, max_length=1000)
    task_type: Literal["COACH", "WEEKLY_REVIEW", "PROPOSAL"]
    facts: dict[str, JsonValue]
    reflect_facts: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_relations: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=20)
    expected_fact_assertions: list[FactAssertion] = Field(default_factory=list, max_length=20)
    expected_decision_domains: list[ExpectedDomain] = Field(default_factory=list, max_length=20)
    expected_readiness: DecisionReadiness
    expected_required_warnings: list[str] = Field(default_factory=list, max_length=12)
    expected_forbidden_claims: list[str] = Field(default_factory=list, max_length=20)
    expected_tool_behavior: ExpectedToolBehavior = Field(default_factory=ExpectedToolBehavior)
    expected_reflect_behavior: ExpectedReflectBehavior = Field(
        default_factory=ExpectedReflectBehavior
    )
    proposal_expected_status: Literal["READY", "BLOCKED", "NOT_APPLICABLE"] = (
        "NOT_APPLICABLE"
    )
    pilot: bool = False
    safety_case: bool = False

    @model_validator(mode="after")
    def validate_case_contract(self) -> "CompetitionAblationCase":
        fact_ids = [item.fact_id for item in self.expected_fact_assertions]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("expected fact IDs must be unique")
        domains = [item.domain for item in self.expected_decision_domains]
        if len(domains) != len(set(domains)):
            raise ValueError("expected decision domains must be unique")
        if self.task_type == "PROPOSAL" and self.proposal_expected_status == "NOT_APPLICABLE":
            raise ValueError("proposal cases require an expected proposal status")
        if self.expected_reflect_behavior.resolvable and not self.reflect_facts:
            raise ValueError("resolvable reflect cases require reflect_facts")
        return self


class AblationDecision(AblationModel):
    domain: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    decision: str = Field(min_length=1, max_length=120)
    support_ids: list[str] = Field(default_factory=list, max_length=20)
    certainty: Literal["LIMITED", "SUPPORTED", "ABSOLUTE"] = "LIMITED"


class AblationProviderOutput(AblationModel):
    """Transient model output. Narrative is scored in memory and never reported."""

    completed: bool
    global_blocked: bool
    answer: str = Field(min_length=1, max_length=6000)
    fact_assertions: dict[str, JsonValue] = Field(default_factory=dict, max_length=30)
    decisions: list[AblationDecision] = Field(default_factory=list, max_length=20)
    warning_codes: list[str] = Field(default_factory=list, max_length=20)
    limitation_codes: list[str] = Field(default_factory=list, max_length=20)
    detected_conflicts: list[str] = Field(default_factory=list, max_length=20)
    proposal_status: Literal["READY", "BLOCKED", "NOT_APPLICABLE"] = "NOT_APPLICABLE"


class MetricFraction(AblationModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)

    @property
    def value(self) -> float:
        return self.numerator / self.denominator if self.denominator else 0.0


class RunMetrics(AblationModel):
    fact_consistency: MetricFraction
    supported_decision: MetricFraction
    unsupported_decision: MetricFraction
    task_completion: MetricFraction
    partial_facts_response: MetricFraction
    false_global_block: MetricFraction
    conflict_detection: MetricFraction
    conflict_overclaim: MetricFraction
    duplicate_evidence_influence: MetricFraction
    reflect_trigger_precision: MetricFraction
    reflect_resolution: MetricFraction
    duplicate_tool_call: MetricFraction
    unsupported_tool_request: MetricFraction
    no_gain_reflect: MetricFraction
    infinite_reflect_loop: MetricFraction
    blocked_domain_hallucination: MetricFraction
    rule_violation: MetricFraction
    warning_retention: MetricFraction
    limitation_retention: MetricFraction
    source_hallucination: MetricFraction
    unauthorized_plan_modification: MetricFraction


class EfficiencyMetrics(AblationModel):
    provider_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    reflect_calls: int = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float = Field(ge=0)
    provider_retry_count: int = Field(ge=0)


class CompetitionCaseRun(AblationModel):
    case_id: str
    category: AblationCategory
    variant: AblationVariant
    run_index: int = Field(ge=1)
    status: Literal["SUCCEEDED", "SCHEMA_FAILED", "PROVIDER_FAILED", "SCORING_FAILED"]
    metrics: RunMetrics
    efficiency: EfficiencyMetrics
    assertion_codes: list[str] = Field(default_factory=list, max_length=80)
    safe_error_codes: list[str] = Field(default_factory=list, max_length=20)


class VariantSummary(AblationModel):
    variant: AblationVariant
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    metric_means: dict[str, float]
    metric_fractions: dict[str, MetricFraction]
    average_latency_ms: float = Field(ge=0)
    latency_std_ms: float = Field(ge=0)
    average_total_tokens: float = Field(ge=0)
    token_std: float = Field(ge=0)
    provider_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    reflect_calls: int = Field(ge=0)


class CompetitionAblationReport(AblationModel):
    evaluation_version: str = "competition-ablation-1.0.0"
    case_set_version: str = "competition-cases-v1"
    phase: Literal["pilot", "full", "safety"]
    generated_at: datetime
    git_commit: str
    provider_mode: Literal["offline", "real"]
    provider_alias: str
    model_alias: str
    thinking_mode: str
    temperature: float
    max_output_tokens: int
    runs_per_case: int
    case_count: int
    total_model_calls: int
    summaries: list[VariantSummary]
    runs: list[CompetitionCaseRun]
    limitations: list[str] = Field(default_factory=list)

