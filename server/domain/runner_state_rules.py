from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

RULESET_VERSION_PATTERN = re.compile(r"^runner-state-rules-\d+\.\d+\.\d+$")


class StrictRulesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataSufficiencyRules(StrictRulesModel):
    minimum_valid_workouts_28d: int = Field(ge=1)
    minimum_active_weeks_28d: int = Field(ge=1, le=4)
    minimum_previous_21d_workouts: int = Field(ge=1)
    minimum_previous_21d_active_weeks: int = Field(ge=1, le=3)
    minimum_rpe_coverage: float = Field(ge=0, le=1)
    minimum_planned_sessions_for_consistency: int = Field(ge=1)
    minimum_available_fatigue_signals: int = Field(ge=1, le=5)


class VolumeTrendRules(StrictRulesModel):
    decreasing_below: float = Field(gt=0)
    stable_upper: float = Field(gt=0)
    increasing_upper: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> VolumeTrendRules:
        if not self.decreasing_below < self.stable_upper < self.increasing_upper:
            raise ValueError("volume_trend thresholds must be strictly increasing")
        return self


class ConsistencyRules(StrictRulesModel):
    high_completion_rate: float = Field(ge=0, le=1)
    moderate_completion_rate: float = Field(ge=0, le=1)
    high_active_weeks: int = Field(ge=1, le=4)
    moderate_active_weeks: int = Field(ge=1, le=4)
    high_weekly_session_cv: float = Field(ge=0)
    moderate_weekly_session_cv: float = Field(ge=0)
    minimum_average_sessions_per_week_for_high: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> ConsistencyRules:
        if self.moderate_completion_rate > self.high_completion_rate:
            raise ValueError("moderate completion threshold cannot exceed high threshold")
        if self.moderate_active_weeks > self.high_active_weeks:
            raise ValueError("moderate active-week threshold cannot exceed high threshold")
        if self.high_weekly_session_cv > self.moderate_weekly_session_cv:
            raise ValueError("high consistency CV cannot exceed moderate consistency CV")
        return self


class FatigueRules(StrictRulesModel):
    rpe_delta_moderate: float = Field(ge=0)
    rpe_delta_high: float = Field(ge=0)
    completion_rate_drop: float = Field(ge=0, le=1)
    frequent_high_intensity_sessions: int = Field(ge=1)
    consecutive_high_intensity_days: int = Field(ge=1)
    elevated_score: int = Field(ge=1)
    high_score: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> FatigueRules:
        if self.rpe_delta_moderate > self.rpe_delta_high:
            raise ValueError("moderate RPE delta cannot exceed high RPE delta")
        if self.elevated_score >= self.high_score:
            raise ValueError("elevated fatigue score must be below high score")
        return self


class RunnerStateRules(StrictRulesModel):
    version: str
    data_sufficiency: DataSufficiencyRules
    volume_trend: VolumeTrendRules
    consistency: ConsistencyRules
    fatigue: FatigueRules

    @model_validator(mode="after")
    def validate_version(self) -> RunnerStateRules:
        if not RULESET_VERSION_PATTERN.fullmatch(self.version):
            raise ValueError("version must use runner-state-rules-X.Y.Z format")
        return self
