from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from server.schemas.planned_workout import PlannedWorkoutWithLogRead
from server.schemas.training_cycle import TrainingCycleRead


class TaskItemRead(BaseModel):
    task_key: str
    task_type: str
    title: str
    description: str | None = None
    priority: int = 50
    count: int = 1
    action_path: str
    source_type: str | None = None
    source_id: int | None = None
    created_at: datetime | None = None


class TaskListResponse(BaseModel):
    items: list[TaskItemRead]
    total: int


class DataSyncProviderSummary(BaseModel):
    provider: str
    connected: bool
    status: str
    masked_account_identifier: str | None = None
    auto_import_enabled: bool = True
    auto_sync_enabled: bool = False
    auto_sync_last_run_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    last_error_code: str | None = None


class DataSyncSummaryRead(BaseModel):
    providers: list[DataSyncProviderSummary]
    connected_count: int = 0
    needs_review_count: int = 0
    failed_job_count: int = 0


class DataSyncPreferencesUpdate(BaseModel):
    auto_import_enabled: bool | None = None
    auto_sync_enabled: bool | None = None


class TrainingPlanOverviewRead(BaseModel):
    has_active_cycle: bool
    active_cycle: TrainingCycleRead | None = None
    current_block: dict[str, Any] | None = None
    week_start: date
    week_end: date
    week_workouts: list[PlannedWorkoutWithLogRead]
    primary_actions: list[dict[str, str]]
    advanced_links: list[dict[str, str]]


class TodayDashboardRead(BaseModel):
    today: date
    has_active_cycle: bool
    workouts: list[PlannedWorkoutWithLogRead]
    tasks: list[TaskItemRead]
    data_sync: DataSyncSummaryRead
    recovery_checkin_completed: bool


class RecoveryQuickPayload(BaseModel):
    leg_feeling: str = Field(pattern="^(good|normal|bad)$")
    fatigue: str = Field(pattern="^(low|normal|high)$")
    pain: str = Field(pattern="^(none|mild|obvious)$")


class RecoveryQuickRead(BaseModel):
    checkin_date: date
    leg_feeling: str | None = None
    fatigue: str | None = None
    pain: str | None = None
    raw: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)
