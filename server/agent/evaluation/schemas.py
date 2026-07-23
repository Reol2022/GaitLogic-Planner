from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.agent.enums import AgentIntent
from server.agent.tools.factory import COACH_AGENT_TOOL_NAMES

EVALUATION_VERSION = "coach-agent-eval-1.0.0"
CASE_SET_VERSION = "cases-v1"

TodayDecision = Literal[
    "PROCEED",
    "PROCEED_WITH_CAUTION",
    "CONSIDER_ADJUSTMENT",
    "REST_OR_RECOVERY",
    "UNKNOWN",
]
PlannedWorkoutStatus = Literal[
    "PLANNED",
    "REST_DAY",
    "NO_PLAN",
    "CYCLE_NOT_ACTIVE",
    "UNKNOWN",
]
PublicQueryStatus = Literal[
    "SUCCEEDED",
    "DEGRADED",
    "VALIDATION_FAILED",
    "REJECTED",
    "UNAVAILABLE",
]


class EvaluationCategory(str, Enum):
    TODAY_RECOMMENDATION = "today_recommendation"
    EXPLAIN_RUNNER_STATE = "explain_runner_state"
    GENERAL_TRAINING_QUESTION = "general_training_question"
    UNKNOWN_DATA = "unknown_data"
    DEGRADED = "degraded"
    SECURITY = "security"


class EvaluationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CoachEvaluationCase(EvaluationContract):
    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    category: EvaluationCategory
    title: str = Field(min_length=1, max_length=160)
    question: str = Field(min_length=1, max_length=4000)
    intent: AgentIntent
    fixture: str = Field(min_length=1, max_length=80)
    expected_status: list[PublicQueryStatus] = Field(min_length=1)
    expected_context_tools: list[str] = Field(default_factory=list)
    expected_model_tools: list[str] = Field(default_factory=list)
    allowed_extra_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    expected_decision: TodayDecision | None = None
    expected_planned_status: PlannedWorkoutStatus | None = None
    required_warning_codes: list[str] = Field(default_factory=list)
    requires_limitation: bool = False
    forbidden_claims: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_public_contract(self) -> "CoachEvaluationCase":
        public_intents = {
            AgentIntent.TODAY_RECOMMENDATION,
            AgentIntent.EXPLAIN_RUNNER_STATE,
            AgentIntent.GENERAL_TRAINING_QUESTION,
        }
        if self.intent not in public_intents:
            raise ValueError("intent must be a currently public Coach intent")
        tool_fields = (
            self.expected_context_tools,
            self.expected_model_tools,
            self.allowed_extra_tools,
            self.forbidden_tools,
        )
        unknown = {name for values in tool_fields for name in values} - COACH_AGENT_TOOL_NAMES
        if unknown:
            raise ValueError(f"unknown Coach tool(s): {sorted(unknown)}")
        if len(self.expected_status) != len(set(self.expected_status)):
            raise ValueError("expected_status must be unique")
        if self.intent == AgentIntent.TODAY_RECOMMENDATION:
            if self.expected_decision is None or self.expected_planned_status is None:
                raise ValueError("today cases require decision and planned status")
        elif self.expected_decision is not None or self.expected_planned_status is not None:
            raise ValueError("non-today cases cannot assert a today recommendation")
        return self


class EvaluationAssertion(EvaluationContract):
    code: str
    passed: bool
    detail: str


class EvaluationCaseResult(EvaluationContract):
    case_id: str
    category: EvaluationCategory
    passed: bool
    intent: AgentIntent
    actual_intent: AgentIntent
    status: PublicQueryStatus
    expected_tools: list[str]
    actual_context_tools: list[str]
    actual_model_tools: list[str]
    expected_decision: TodayDecision | None = None
    actual_decision: TodayDecision | None = None
    expected_planned_status: PlannedWorkoutStatus | None = None
    actual_planned_status: PlannedWorkoutStatus | None = None
    assertions: list[EvaluationAssertion]
    safe_error_codes: list[str]
    duration_ms: float = Field(ge=0)
    used_fallback: bool
    required_tool_hits: int = Field(ge=0)
    required_tool_total: int = Field(ge=0)
    forbidden_tool_called: bool
    tool_arguments_valid: bool
    warning_retained: bool | None = None
    limitation_retained: bool | None = None
    unsupported_claim_found: bool
    rule_violation_found: bool


class EvaluationSummary(EvaluationContract):
    total_cases: int
    passed_cases: int
    case_pass_rate: float
    intent_accuracy: float
    required_tool_recall: float
    forbidden_tool_call_rate: float
    tool_argument_validity: float
    decision_consistency: float
    planned_status_consistency: float
    warning_retention_rate: float
    limitation_retention_rate: float
    fallback_success_rate: float
    unsupported_claim_rate: float
    rule_violation_rate: float


class CategorySummary(EvaluationContract):
    total_cases: int
    passed_cases: int
    pass_rate: float


class CoachEvaluationReport(EvaluationContract):
    evaluation_version: str = EVALUATION_VERSION
    case_set_version: str = CASE_SET_VERSION
    prompt_version: str
    git_commit: str
    generated_at: datetime
    duration_ms: float = Field(ge=0)
    summary: EvaluationSummary
    categories: dict[str, CategorySummary]
    cases: list[EvaluationCaseResult]
