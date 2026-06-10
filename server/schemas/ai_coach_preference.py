from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AICoachPreferenceBase(BaseModel):
    preferred_training_systems: list[str] = Field(default_factory=list, max_length=12)
    intensity_conservatism: str = Field(default="standard", max_length=32)
    key_workout_habit: str | None = Field(default=None, max_length=1000)
    rest_day_strategy: str | None = Field(default=None, max_length=1000)
    disabled_workout_types: list[str] = Field(default_factory=list, max_length=16)
    double_run_policy: str = Field(default="cautious", max_length=32)
    long_run_strategy: str | None = Field(default=None, max_length=1000)
    injury_risk_policy: str | None = Field(default=None, max_length=1000)
    additional_notes: str | None = Field(default=None, max_length=1500)


class AICoachPreferenceUpdate(AICoachPreferenceBase):
    pass


class AICoachPreferenceRead(AICoachPreferenceBase):
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
