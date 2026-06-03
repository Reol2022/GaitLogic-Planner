from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaceRuleBase(BaseModel):
    code: str
    name: str
    target_pace_text: str | None = None
    physiological_purpose: str | None = None
    note: str | None = None
    sort_order: int


class PaceRuleCreate(PaceRuleBase):
    pass


class PaceRuleUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    target_pace_text: str | None = None
    physiological_purpose: str | None = None
    note: str | None = None
    sort_order: int | None = None


class PaceRuleRead(PaceRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

