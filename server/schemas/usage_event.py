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
