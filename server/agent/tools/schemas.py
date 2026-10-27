from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from server.agent.schemas import AgentContractModel, AgentNotice


class TrainingDataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    NOT_FOUND = "NOT_FOUND"


class EmptyToolInput(AgentContractModel):
    pass


class WorkoutDateInput(AgentContractModel):
    target_date: date | None = None


class AgentEvidenceRead(AgentContractModel):
    metric: str = Field(max_length=80)
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    unit: str | None = Field(default=None, max_length=32)
    window: str = Field(max_length=32)
    source: str = Field(max_length=80)
    used: bool


class AgentDataQualityRead(AgentContractModel):
    level: str
    completeness: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list, max_length=30)


class RunnerStateToolOutput(AgentContractModel):
    data_status: TrainingDataStatus
    as_of_date: date
    overall_state: str
    risk_level: str
    data_quality: AgentDataQualityRead
    metrics: dict[str, float | int | str | None]
    evidence: list[AgentEvidenceRead] = Field(default_factory=list, max_length=20)
    warnings: list[AgentNotice] = Field(default_factory=list, max_length=20)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)
    overall_readiness: str | None = None
    domain_readiness: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    hard_blockers: list[str] = Field(default_factory=list, max_length=20)
    data_limitations: list[str] = Field(default_factory=list, max_length=20)
    capability_limitations: list[str] = Field(default_factory=list, max_length=20)


class RunnerStateHistoryInput(AgentContractModel):
    limit: int = Field(default=7, ge=1, le=14)


class RunnerStateHistoryItem(AgentContractModel):
    snapshot_id: int
    captured_at: datetime
    trigger_type: str
    overall_state: str
    risk_level: str
    selected_metrics: dict[str, float | int | str | None]
    data_quality: float | None = Field(default=None, ge=0, le=1)


class RunnerStateHistoryOutput(AgentContractModel):
    data_status: TrainingDataStatus
    items: list[RunnerStateHistoryItem] = Field(default_factory=list, max_length=14)
    trend_summary: str | None = Field(default=None, max_length=300)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)


class RecentTrainingInput(AgentContractModel):
    days: int | None = Field(default=None, ge=1, le=28)
    start_date: date | None = None
    end_date: date | None = None
    range_kind: str | None = Field(default=None, max_length=40)
    range_label: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_range(self) -> "RecentTrainingInput":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date must not be after end_date")
            if (self.end_date - self.start_date).days >= 120:
                raise ValueError("training range cannot exceed 120 days")
        return self


class RecentTrainingItem(AgentContractModel):
    date: date
    planned_date: date | None = None
    training_type: str
    classification_basis: str = "ACTUAL_LOG"
    association_status: str = "UNPLANNED"
    planned_or_unplanned: str
    completion_status: str
    distance_km: float | None = None
    duration_seconds: int | None = None
    average_pace_seconds_per_km: int | None = None
    average_heart_rate: int | None = None
    rpe: int | None = None
    source: str
    brief_review: str | None = Field(default=None, max_length=240)


class RecentTrainingSummary(AgentContractModel):
    total_sessions: int
    total_distance_km: float | None = None
    completed_key_sessions: int
    rest_days: int
    planned_sessions_due: int = 0
    completed_planned_sessions: int = 0
    unplanned_sessions: int = 0
    completion_rate: float | None = Field(default=None, ge=0, le=1)


class TrainingFactIssue(AgentContractModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=240)
    affected_metrics: list[str] = Field(default_factory=list, max_length=10)


class RecentTrainingOutput(AgentContractModel):
    data_status: TrainingDataStatus
    as_of: date
    range_start: date | None = None
    range_end: date | None = None
    range_kind: str = Field(default="LEGACY_WINDOW", max_length=40)
    range_label: str = Field(default="训练统计区间", max_length=80)
    items: list[RecentTrainingItem] = Field(default_factory=list, max_length=50)
    details_complete: bool = True
    summary: RecentTrainingSummary
    data_quality: AgentDataQualityRead
    fact_issues: list[TrainingFactIssue] = Field(default_factory=list, max_length=20)
    missing_reasons: list[str] = Field(default_factory=list, max_length=20)


class TodayWorkoutOutput(AgentContractModel):
    data_status: TrainingDataStatus
    workout_status: Literal["PLANNED", "REST_DAY", "NO_PLAN", "CYCLE_NOT_ACTIVE", "UNKNOWN"]
    date: date
    training_type: str | None = None
    title: str | None = Field(default=None, max_length=160)
    distance_or_duration_target: str | None = Field(default=None, max_length=160)
    pace_target: str | None = Field(default=None, max_length=160)
    heart_rate_target: str | None = Field(default=None, max_length=160)
    segments: list[str] = Field(default_factory=list, max_length=12)
    notes: str | None = Field(default=None, max_length=500)
    completion_status: str | None = None
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)


class TrainingCycleBlockRead(AgentContractModel):
    name: str = Field(max_length=128)
    start_date: date | None = None
    end_date: date | None = None
    phase: str | None = Field(default=None, max_length=128)
    focus: str | None = Field(default=None, max_length=240)


class CurrentTrainingCycleOutput(AgentContractModel):
    data_status: TrainingDataStatus
    lifecycle_status: str | None = None
    transition: str | None = None
    cycle_id: int | None = None
    name: str | None = Field(default=None, max_length=128)
    start_date: date | None = None
    end_date: date | None = None
    target_race_name: str | None = Field(default=None, max_length=128)
    target_race_date: date | None = None
    current_phase: str | None = Field(default=None, max_length=128)
    goal: str | None = Field(default=None, max_length=255)
    progress: float | None = Field(default=None, ge=0, le=1)
    weekly_structure: list[TrainingCycleBlockRead] = Field(default_factory=list, max_length=16)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)


class TrainingPlanWindowInput(AgentContractModel):
    start_date: date
    end_date: date
    prefer_confirmed_race_date: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> "TrainingPlanWindowInput":
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if (self.end_date - self.start_date).days > 42:
            raise ValueError("plan window cannot exceed 43 days")
        return self


class TrainingPlanWindowItem(AgentContractModel):
    date: date
    training_type: str
    title: str = Field(max_length=160)
    planned_distance_km: float | None = None
    completion_status: str | None = None


class TrainingPlanWindowOutput(AgentContractModel):
    data_status: TrainingDataStatus
    range_start: date
    range_end: date
    range_source: str = Field(default="REQUESTED_RANGE", max_length=40)
    items: list[TrainingPlanWindowItem] = Field(default_factory=list, max_length=43)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)


class TrainingRulesInput(AgentContractModel):
    scope: Literal["TODAY", "WEEK", "RUNNER_STATE", "GENERAL"]


class TrainingRuleSummaryRead(AgentContractModel):
    rule_id: str
    name: str = Field(max_length=160)
    category: str = Field(max_length=80)
    summary: str | None = Field(default=None, max_length=300)
    severity: str
    evidence_required: list[str] = Field(default_factory=list, max_length=20)


class TrainingRulesOutput(AgentContractModel):
    data_status: TrainingDataStatus
    rules: list[TrainingRuleSummaryRead] = Field(default_factory=list, max_length=50)
    source_version: str
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)


class TodayEvaluationRuleHit(AgentContractModel):
    rule_code: str
    severity: str
    action: str
    explanation: str = Field(max_length=300)


class TodayEvaluationOutput(AgentContractModel):
    data_status: TrainingDataStatus
    decision: str
    risk_level: str
    rule_hits: list[TodayEvaluationRuleHit] = Field(default_factory=list, max_length=20)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[AgentNotice] = Field(default_factory=list, max_length=20)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)


class TrainingDataQualityInput(AgentContractModel):
    window_days: int = Field(default=14, ge=1, le=120)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "TrainingDataQualityInput":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date must not be after end_date")
            if (self.end_date - self.start_date).days >= 120:
                raise ValueError("quality range cannot exceed 120 days")
        return self


class TrainingDataQualityOutput(AgentContractModel):
    data_status: TrainingDataStatus
    window_days: int
    coverage: dict[str, float]
    missing_fields: list[str] = Field(default_factory=list, max_length=30)
    source_mix: dict[str, int]
    freshness: str
    warnings: list[AgentNotice] = Field(default_factory=list, max_length=20)
    limitations: list[AgentNotice] = Field(default_factory=list, max_length=20)
