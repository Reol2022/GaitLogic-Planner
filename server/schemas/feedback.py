from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import FeedbackType


class FeedbackCreate(BaseModel):
    feedback_type: FeedbackType
    page_url: str | None = Field(default=None, max_length=512)
    content: str = Field(..., min_length=1)
    contact: str | None = Field(default=None, max_length=255)


class FeedbackRead(BaseModel):
    id: int
    feedback_type: FeedbackType
    page_url: str | None = None
    content: str
    contact: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
