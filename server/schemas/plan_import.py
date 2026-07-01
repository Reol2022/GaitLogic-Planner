from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from planner_core.enums import PlanAdjustmentDraftStatus

AnchorStrategy = Literal["after_last_completed", "explicit_date"]
MergeStrategy = Literal[
    "replace_uncompleted_from_date",
    "replace_uncompleted_in_range",
    "append_after_last_planned",
    "fill_empty_only",
]
SourceType = Literal["structured_json", "json_file", "xlsx", "csv", "txt", "markdown"]
PlanImportOperation = Literal["create", "update", "remove", "preserve", "conflict"]


class PlanImportWorkoutItem(BaseModel):
    planned_date: date | None = None
    day_offset: int | None = None
    session_index: int = Field(default=1, ge=1, le=9)
    workout_type: str
    title: str | None = None
    planned_distance_km: Decimal | None = Field(default=None, ge=0)
    planned_duration_minutes: int | None = Field(default=None, ge=0)
    target_pace: str | None = None
    target_rpe: int | None = Field(default=None, ge=1, le=10)
    content: str
    notes: str | None = None
    is_rest_day: bool = False
    segments: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def validate_date_pointer(self) -> "PlanImportWorkoutItem":
        if self.planned_date is None and self.day_offset is None:
            raise ValueError("planned_date 和 day_offset 必须二选一")
        return self


class PlanImportStructuredRequest(BaseModel):
    target_cycle_id: int | None = None
    target_block_id: int | None = None
    source: str = "structured_json"
    client_request_id: str
    anchor_strategy: AnchorStrategy = "after_last_completed"
    effective_date: date | None = None
    merge_strategy: MergeStrategy = "replace_uncompleted_in_range"
    timezone: str = "Asia/Shanghai"
    workouts: list[PlanImportWorkoutItem]

    @field_validator("workouts")
    @classmethod
    def workouts_not_empty(cls, value: list[PlanImportWorkoutItem]) -> list[PlanImportWorkoutItem]:
        if not value:
            raise ValueError("workouts 不能为空")
        if len(value) > 370:
            raise ValueError("单次导入最多支持 370 条训练")
        return value


class PlanImportDiffSummary(BaseModel):
    preserved_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    removed_count: int = 0
    protected_count: int = 0
    conflict_count: int = 0
    warning_count: int = 0


class PlanImportIssue(BaseModel):
    code: str
    message: str
    planned_date: date | None = None
    session_index: int | None = None
    row: int | None = None
    column: str | None = None


class PlanImportItemRead(BaseModel):
    id: int
    draft_id: int
    planned_workout_id: int | None
    operation: str | None
    planned_date: date | None
    session_index: int | None
    original_content: str
    suggested_content: str
    original_distance_km: Decimal | None
    suggested_distance_km: Decimal | None
    original_main_type: str | None
    suggested_main_type: str | None
    original_target_pace_text: str | None
    suggested_target_pace_text: str | None
    reason: str
    is_selected: bool
    is_applied: bool
    normalized_item_json: dict[str, Any] | None = None
    conflict_json: list[dict[str, Any]] | None = None
    warnings_json: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)


class PlanImportDraftRead(BaseModel):
    import_id: int = Field(validation_alias="id")
    status: PlanAdjustmentDraftStatus
    effective_date: date | None
    source_type: str | None
    source_name: str | None
    source_filename: str | None
    parser_version: str | None
    merge_strategy: str | None
    anchor_strategy: str | None
    target_cycle_id: int | None
    target_block_id: int | None
    normalized_items: list[dict[str, Any]] | None = Field(default_factory=list, validation_alias="normalized_payload_json")
    diff_summary: dict[str, Any] | None = Field(default=None, validation_alias="diff_summary_json")
    conflicts: list[dict[str, Any]] | None = Field(default_factory=list, validation_alias="conflict_summary_json")
    warnings: list[dict[str, Any]] | None = Field(default_factory=list, validation_alias="warnings_json")
    client_request_id: str | None
    expires_at: datetime | None
    applied_at: datetime | None
    cancelled_at: datetime | None
    items: list[PlanImportItemRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PlanImportCreateResponse(BaseModel):
    import_id: int
    status: PlanAdjustmentDraftStatus
    effective_date: date
    normalized_items: list[dict[str, Any]]
    diff_summary: PlanImportDiffSummary
    conflicts: list[PlanImportIssue]
    warnings: list[PlanImportIssue]


class PlanImportItemUpdate(BaseModel):
    planned_date: date | None = None
    day_offset: int | None = None
    session_index: int | None = Field(default=None, ge=1, le=9)
    workout_type: str | None = None
    title: str | None = None
    planned_distance_km: Decimal | None = Field(default=None, ge=0)
    planned_duration_minutes: int | None = Field(default=None, ge=0)
    target_pace: str | None = None
    target_rpe: int | None = Field(default=None, ge=1, le=10)
    content: str | None = None
    notes: str | None = None
    is_rest_day: bool | None = None
    segments: list[dict[str, Any]] | None = None


class PlanImportApplyResponse(BaseModel):
    import_id: int
    status: PlanAdjustmentDraftStatus
    diff_summary: PlanImportDiffSummary
