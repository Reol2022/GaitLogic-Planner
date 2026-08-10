from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationModel(BaseModel):
    """Strict safe schema shared by public evaluation adapters and reports."""

    model_config = ConfigDict(extra="forbid")


class EvaluationFailureCategory(str, Enum):
    BUSINESS_FAILURE = "BUSINESS_FAILURE"
    RULE_FAILURE = "RULE_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    VALIDATOR_FAILURE = "VALIDATOR_FAILURE"
    FALLBACK_FAILURE = "FALLBACK_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    ENVIRONMENT_BLOCKER = "ENVIRONMENT_BLOCKER"


class EvaluationRunStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class EvaluationMetric(EvaluationModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,100}$")
    category: str = Field(pattern=r"^[A-Z][A-Z_]{1,64}$")
    current: float
    baseline: float | None = None
    delta: float | None = None


class EvaluationGateResult(EvaluationModel):
    name: str
    metric: str
    comparator: Literal["gte", "lte"]
    expected: float
    actual: float | None = None
    passed: bool
    safety_critical: bool = False
    baseline_based: bool = False


class EvaluationCaseResult(EvaluationModel):
    case_id: str
    category: str
    passed: bool
    failure_category: EvaluationFailureCategory | None = None
    safe_error_codes: list[str] = Field(default_factory=list)


class EvaluationSuiteResult(EvaluationModel):
    suite: str
    version: str
    started_at: datetime
    duration_ms: float = Field(ge=0)
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    skipped_cases: int = Field(ge=0)
    metrics: list[EvaluationMetric] = Field(default_factory=list)
    gates: list[EvaluationGateResult] = Field(default_factory=list)
    provider_mode: Literal["offline", "real"]
    dataset_type: Literal["public_fictional"]
    status: EvaluationRunStatus
    cases: list[EvaluationCaseResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EvaluationRun(EvaluationModel):
    evaluation_version: str = "gaitlogic-agent-regression-1.0.0"
    run_id: str
    started_at: datetime
    duration_ms: float = Field(ge=0)
    provider_mode: Literal["offline", "real"]
    baseline_version: str
    status: EvaluationRunStatus
    suites: list[EvaluationSuiteResult]


class EvaluationBaselineSuite(EvaluationModel):
    version: str
    dataset_version: str
    metrics: dict[str, float]


class EvaluationBaselineManifest(EvaluationModel):
    baseline_version: str
    product_version: str
    created_at: datetime
    suites: dict[str, EvaluationBaselineSuite]
