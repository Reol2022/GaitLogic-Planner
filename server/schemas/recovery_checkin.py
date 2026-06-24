from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import PainTrend, RecoveryCheckinSource


class RecoveryCheckinPayload(BaseModel):
    sleep_duration_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    sleep_quality: int | None = Field(default=None, ge=1, le=5)
    subjective_fatigue: int | None = Field(default=None, ge=1, le=5)
    muscle_soreness: int | None = Field(default=None, ge=1, le=5)
    stress_level: int | None = Field(default=None, ge=1, le=5)
    mood_level: int | None = Field(default=None, ge=1, le=5)
    leg_feeling: int | None = Field(default=None, ge=1, le=5)
    resting_heart_rate_bpm: int | None = Field(default=None, ge=20, le=240)
    hrv_value: Decimal | None = Field(default=None, ge=0, le=1000)
    hrv_metric: str | None = Field(default=None, max_length=32)
    hrv_source: str | None = Field(default=None, max_length=64)
    pain_level: int | None = Field(default=None, ge=0, le=10)
    pain_location: str | None = Field(default=None, max_length=128)
    pain_trend: PainTrend = PainTrend.unknown
    pain_affects_gait: bool | None = None
    illness_symptoms: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class RecoveryCheckinRead(RecoveryCheckinPayload):
    id: int
    checkin_date: date
    source: RecoveryCheckinSource
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryCheckinListResponse(BaseModel):
    items: list[RecoveryCheckinRead]
