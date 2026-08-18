from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class UnknownState(str, Enum):
    UNKNOWN = "UNKNOWN"


class DataQualityLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class VolumeTrendState(str, Enum):
    UNKNOWN = "UNKNOWN"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    INCREASING = "INCREASING"
    SPIKING = "SPIKING"


class TrainingConsistencyState(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class FatigueState(str, Enum):
    UNKNOWN = "UNKNOWN"
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"


class TrainingPhaseState(str, Enum):
    UNKNOWN = "UNKNOWN"
    BASE = "BASE"
    BUILD = "BUILD"
    SPECIFIC = "SPECIFIC"
    PEAK = "PEAK"
    TAPER = "TAPER"
    RACE = "RACE"
    RECOVERY = "RECOVERY"


class InferenceBasis(str, Enum):
    PLAN_COMPLETION = "PLAN_COMPLETION"
    ACTIVITY_REGULARITY = "ACTIVITY_REGULARITY"


class ReasonCode(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INSUFFICIENT_BASELINE_DATA = "INSUFFICIENT_BASELINE_DATA"
    INSUFFICIENT_RPE_COVERAGE = "INSUFFICIENT_RPE_COVERAGE"
    INSUFFICIENT_PLAN_DATA = "INSUFFICIENT_PLAN_DATA"
    INSUFFICIENT_FATIGUE_SIGNALS = "INSUFFICIENT_FATIGUE_SIGNALS"
    RECENT_VOLUME_BELOW_BASELINE = "RECENT_VOLUME_BELOW_BASELINE"
    RECENT_VOLUME_STABLE = "RECENT_VOLUME_STABLE"
    RECENT_VOLUME_ABOVE_BASELINE = "RECENT_VOLUME_ABOVE_BASELINE"
    RECENT_VOLUME_SPIKE = "RECENT_VOLUME_SPIKE"
    HIGH_PLAN_COMPLETION = "HIGH_PLAN_COMPLETION"
    MODERATE_PLAN_COMPLETION = "MODERATE_PLAN_COMPLETION"
    LOW_PLAN_COMPLETION = "LOW_PLAN_COMPLETION"
    STABLE_ACTIVITY_FREQUENCY = "STABLE_ACTIVITY_FREQUENCY"
    MODERATE_ACTIVITY_FREQUENCY = "MODERATE_ACTIVITY_FREQUENCY"
    UNSTABLE_ACTIVITY_FREQUENCY = "UNSTABLE_ACTIVITY_FREQUENCY"
    TRAINING_PHASE_UNAVAILABLE = "TRAINING_PHASE_UNAVAILABLE"
    VOLUME_INCREASE_SIGNAL = "VOLUME_INCREASE_SIGNAL"
    RPE_INCREASE_SIGNAL = "RPE_INCREASE_SIGNAL"
    COMPLETION_DROP_SIGNAL = "COMPLETION_DROP_SIGNAL"
    CONSECUTIVE_HIGH_INTENSITY_SIGNAL = "CONSECUTIVE_HIGH_INTENSITY_SIGNAL"
    FREQUENT_HIGH_INTENSITY_SIGNAL = "FREQUENT_HIGH_INTENSITY_SIGNAL"


class RiskSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ATTENTION = "ATTENTION"


class SuggestedActionType(str, Enum):
    REVIEW = "REVIEW"
    REVIEW_RECOVERY = "REVIEW_RECOVERY"
    REDUCE_LOAD = "REDUCE_LOAD"
    ADD_RECOVERY = "ADD_RECOVERY"
    COLLECT_MORE_DATA = "COLLECT_MORE_DATA"
    MANUAL_CONFIRMATION = "MANUAL_CONFIRMATION"


class RiskFlagCode(str, Enum):
    VOLUME_SPIKE = "VOLUME_SPIKE"
    CONSECUTIVE_HIGH_INTENSITY_DAYS = "CONSECUTIVE_HIGH_INTENSITY_DAYS"
    RPE_ABOVE_BASELINE = "RPE_ABOVE_BASELINE"
    RECENT_COMPLETION_DROP = "RECENT_COMPLETION_DROP"
    FREQUENT_HIGH_INTENSITY_SESSIONS = "FREQUENT_HIGH_INTENSITY_SESSIONS"


class InferenceEvidence(BaseModel):
    metric: str
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    unit: str | None = None
    window: str
    source: str
    used: bool


class WeeklyTrainingBreakdown(BaseModel):
    window_start: date
    window_end: date
    distance_km: float | None = None
    sessions: int = 0
    active: bool = False


class RunnerStateDerivedMetrics(BaseModel):
    calculation_window_start_previous_21d: date
    calculation_window_end_previous_21d: date
    distance_previous_21d_km: float | None = None
    sessions_previous_21d: int = 0
    valid_workout_count_previous_21d: int = 0
    average_rpe_previous_21d: float | None = None
    rpe_coverage_previous_21d: float = Field(default=0, ge=0, le=1)
    planned_sessions_previous_21d: int = 0
    completed_planned_sessions_previous_21d: int = 0
    completion_rate_previous_21d: float | None = None
    active_weeks_previous_21d: int = 0
    active_weeks_28d: int = 0
    weekly_distance_breakdown_28d: list[WeeklyTrainingBreakdown] = Field(default_factory=list)
    weekly_session_breakdown_28d: list[WeeklyTrainingBreakdown] = Field(default_factory=list)
    weekly_session_mean_28d: float = 0
    weekly_session_cv_28d: float | None = None
    high_intensity_sessions_7d: int = 0
    high_intensity_sessions_28d: int = 0
    maximum_consecutive_high_intensity_days_7d: int = 0


class VolumeTrendInference(BaseModel):
    state: VolumeTrendState = VolumeTrendState.UNKNOWN
    previous_21d_weekly_average_km: float | None = None
    volume_ratio: float | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    evidence: list[InferenceEvidence] = Field(default_factory=list)
    ruleset_version: str


class TrainingConsistencyInference(BaseModel):
    state: TrainingConsistencyState = TrainingConsistencyState.UNKNOWN
    basis: InferenceBasis | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    evidence: list[InferenceEvidence] = Field(default_factory=list)
    evidence_coverage: float = Field(default=0, ge=0, le=1)
    ruleset_version: str


class FatigueInference(BaseModel):
    state: FatigueState = FatigueState.UNKNOWN
    score: int = 0
    triggered_signals: list[str] = Field(default_factory=list)
    skipped_signals: list[str] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    evidence: list[InferenceEvidence] = Field(default_factory=list)
    available_signal_count: int = 0
    total_signal_count: int = 5
    evidence_coverage: float = Field(default=0, ge=0, le=1)
    ruleset_version: str


class RunnerStateRiskFlag(BaseModel):
    code: RiskFlagCode
    severity: RiskSeverity
    message: str
    suggested_action_type: SuggestedActionType
    triggered_rule: str
    evidence: list[InferenceEvidence] = Field(default_factory=list)


class RunnerStateInferenceMetadata(BaseModel):
    ruleset_version: str
    calculated_at: datetime
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    overall_readiness: str | None = None
    domain_readiness: list[dict[str, object]] = Field(default_factory=list)
    hard_blockers: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    capability_limitations: list[str] = Field(default_factory=list)


class RunnerIdentityReference(BaseModel):
    runner_id: int
    generated_at: datetime
    timezone: str
    calculation_window_end: date
    calculation_window_start_7d: date
    calculation_window_start_28d: date


class RunnerGoalContext(BaseModel):
    race_distance: str | None = None
    race_date: date | None = None
    target_time_seconds: int | None = None
    weeks_remaining: float | None = None


class RecentTrainingMetrics(BaseModel):
    distance_7d_km: float | None = None
    distance_28d_km: float | None = None
    duration_7d_minutes: float | None = None
    duration_28d_minutes: float | None = None
    sessions_7d: int = 0
    sessions_28d: int = 0
    completed_sessions_7d: int = 0
    completed_sessions_28d: int = 0
    planned_sessions_7d: int = 0
    planned_sessions_28d: int = 0
    completion_rate_7d: float | None = None
    completion_rate_28d: float | None = None
    average_rpe_7d: float | None = None
    average_rpe_28d: float | None = None


class IntensityMetrics(BaseModel):
    easy_distance_7d_km: float | None = None
    moderate_distance_7d_km: float | None = None
    hard_distance_7d_km: float | None = None
    easy_distance_28d_km: float | None = None
    moderate_distance_28d_km: float | None = None
    hard_distance_28d_km: float | None = None
    hard_distance_ratio_7d: float | None = None
    hard_distance_ratio_28d: float | None = None
    quality_sessions_7d: int = 0
    quality_sessions_28d: int = 0
    long_run_distance_7d_km: float | None = None
    long_run_distance_28d_km: float | None = None
    days_since_last_quality_session: int | None = None


class InferredStatePlaceholders(BaseModel):
    fitness_state: UnknownState = UnknownState.UNKNOWN
    fatigue_state: FatigueState = FatigueState.UNKNOWN
    load_trend: UnknownState = UnknownState.UNKNOWN
    training_consistency: TrainingConsistencyState = TrainingConsistencyState.UNKNOWN
    training_phase: TrainingPhaseState = TrainingPhaseState.UNKNOWN
    weaknesses: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class RunnerStateDataQuality(BaseModel):
    data_quality_level: DataQualityLevel
    confidence: float = Field(ge=0, le=1)
    available_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    valid_workout_count_7d: int = 0
    valid_workout_count_28d: int = 0
    rpe_coverage_7d: float = Field(default=0, ge=0, le=1)
    rpe_coverage_28d: float = Field(default=0, ge=0, le=1)
    heart_rate_coverage_7d: float = Field(default=0, ge=0, le=1)
    heart_rate_coverage_28d: float = Field(default=0, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class RunnerStateSnapshot(BaseModel):
    identity: RunnerIdentityReference
    goal_context: RunnerGoalContext
    recent_training: RecentTrainingMetrics
    intensity: IntensityMetrics
    inferred_state: InferredStatePlaceholders
    data_quality: RunnerStateDataQuality
    derived_metrics: RunnerStateDerivedMetrics | None = None
    volume_trend: VolumeTrendInference | None = None
    training_consistency: TrainingConsistencyInference | None = None
    fatigue: FatigueInference | None = None
    risk_flags: list[RunnerStateRiskFlag] = Field(default_factory=list)
    inference_metadata: RunnerStateInferenceMetadata | None = None


class RunnerStateCurrentResponse(BaseModel):
    snapshot: RunnerStateSnapshot
