"""Strict public response contracts for the three read-only MCP tools."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.mcp.errors import McpErrorCode


class McpContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class McpNotice(McpContractModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    message: str = Field(min_length=1, max_length=300)


class McpError(McpContractModel):
    code: McpErrorCode
    message: str = Field(min_length=1, max_length=160)


class McpDataQuality(McpContractModel):
    level: str = Field(min_length=1, max_length=40)
    completeness: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list, max_length=30)


class McpEvidence(McpContractModel):
    metric: str = Field(max_length=80)
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    unit: str | None = Field(default=None, max_length=32)
    window: str = Field(max_length=32)
    source: str = Field(max_length=80)
    used: bool


class McpTodayPlan(McpContractModel):
    data_status: str = Field(min_length=1, max_length=32)
    workout_status: Literal["PLANNED", "REST_DAY", "NO_PLAN", "CYCLE_NOT_ACTIVE", "UNKNOWN"]
    date: date
    training_type: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=160)
    distance_or_duration_target: str | None = Field(default=None, max_length=160)
    pace_target: str | None = Field(default=None, max_length=160)
    completion_status: str | None = Field(default=None, max_length=80)
    limitations: list[McpNotice] = Field(default_factory=list, max_length=20)


class McpRecentTrainingItem(McpContractModel):
    """Public training fact, deliberately excluding free-text workout reviews."""

    date: date
    training_type: str = Field(max_length=80)
    planned_or_unplanned: str = Field(max_length=32)
    completion_status: str = Field(max_length=80)
    distance_km: float | None = None
    duration_seconds: int | None = None
    average_pace_seconds_per_km: int | None = None
    average_heart_rate: int | None = None
    rpe: int | None = Field(default=None, ge=0, le=10)
    source: str = Field(max_length=32)


class McpRecentTrainingSummary(McpContractModel):
    total_sessions: int = Field(ge=0)
    total_distance_km: float | None = Field(default=None, ge=0)
    completed_key_sessions: int = Field(ge=0)
    rest_days: int = Field(ge=0)


class McpRecentTraining(McpContractModel):
    data_status: str = Field(min_length=1, max_length=32)
    as_of: date
    items: list[McpRecentTrainingItem] = Field(default_factory=list, max_length=20)
    summary: McpRecentTrainingSummary
    data_quality: McpDataQuality
    missing_reasons: list[str] = Field(default_factory=list, max_length=20)


class McpRunnerState(McpContractModel):
    data_status: str = Field(min_length=1, max_length=32)
    as_of_date: date
    overall_state: str = Field(max_length=80)
    risk_level: str = Field(max_length=40)
    data_quality: McpDataQuality
    metrics: dict[str, float | int | str | None]
    evidence: list[McpEvidence] = Field(default_factory=list, max_length=15)
    warnings: list[McpNotice] = Field(default_factory=list, max_length=20)
    limitations: list[McpNotice] = Field(default_factory=list, max_length=20)


class _McpToolResult(McpContractModel):
    status: Literal["SUCCEEDED", "FAILED"]
    error: McpError | None = None

    @model_validator(mode="after")
    def validate_error_state(self) -> "_McpToolResult":
        if self.status == "SUCCEEDED" and self.error is not None:
            raise ValueError("successful result cannot include an error")
        if self.status == "FAILED" and self.error is None:
            raise ValueError("failed result requires a safe error")
        return self


class McpTodayPlanResult(_McpToolResult):
    data: McpTodayPlan | None = None

    @model_validator(mode="after")
    def validate_data(self) -> "McpTodayPlanResult":
        if (self.status == "SUCCEEDED") != (self.data is not None):
            raise ValueError("result data must match status")
        return self


class McpRecentTrainingResult(_McpToolResult):
    data: McpRecentTraining | None = None

    @model_validator(mode="after")
    def validate_data(self) -> "McpRecentTrainingResult":
        if (self.status == "SUCCEEDED") != (self.data is not None):
            raise ValueError("result data must match status")
        return self


class McpRunnerStateResult(_McpToolResult):
    data: McpRunnerState | None = None

    @model_validator(mode="after")
    def validate_data(self) -> "McpRunnerStateResult":
        if (self.status == "SUCCEEDED") != (self.data is not None):
            raise ValueError("result data must match status")
        return self
