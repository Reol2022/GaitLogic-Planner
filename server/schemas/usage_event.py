from datetime import date

from pydantic import BaseModel, Field

from planner_core.enums import UsageEventName


class UsageEventCreate(BaseModel):
    event_name: UsageEventName
    page_path: str | None = Field(default=None, max_length=255)
    metadata_json: dict | None = None


class UsageEventAck(BaseModel):
    message: str = "事件已记录"


class ProductMetricsRead(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    onboarding_viewed_users: int
    ai_plan_generate_succeeded_users: int
    ai_plan_applied_users: int
    today_viewed_users: int
    workout_log_saved_users: int
    generate_to_apply_rate: float
    apply_to_first_checkin_rate: float
    training_readiness_allowlisted_users: int = 0
    recovery_checkin_saved_users: int = 0
    readiness_detail_viewed_users: int = 0
    readiness_recalculated_users: int = 0
    reduce_load_suggestion_viewed_users: int = 0
    readiness_assessment_success_count: int = 0
    readiness_status_distribution: dict[str, int] = Field(default_factory=dict)
    readiness_data_quality_distribution: dict[str, int] = Field(default_factory=dict)
