from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol


class ProviderError(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


@dataclass(slots=True)
class ProviderAuthResult:
    status: str
    token_payload: dict[str, Any] | None = None
    account_identifier: str | None = None
    masked_account_identifier: str | None = None
    provider_user_id: str | None = None
    mfa_token: str | None = None
    safe_message: str | None = None


@dataclass(slots=True)
class ProviderLap:
    lap_index: int
    external_lap_id: str | None = None
    start_time: datetime | None = None
    start_offset_seconds: int | None = None
    distance_m: Decimal | None = None
    duration_seconds: int | None = None
    timer_time_seconds: int | None = None
    moving_time_seconds: int | None = None
    average_speed_mps: Decimal | None = None
    average_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None
    average_cadence_spm: int | None = None
    elevation_gain_m: int | None = None
    lap_type: str | None = None
    workout_step_type: str | None = None
    segment_role: str = "unknown"
    classification_source: str = "unknown"
    classification_confidence: str = "low"
    data_quality: str = "valid"


@dataclass(slots=True)
class ProviderActivity:
    external_activity_id: str
    activity_name: str | None
    activity_type: str
    activity_subtype: str | None
    start_time_local: datetime
    timezone: str = "Asia/Shanghai"
    start_time_utc: datetime | None = None
    source_updated_at: datetime | None = None
    distance_m: Decimal | None = None
    duration_seconds: int | None = None
    timer_time_seconds: int | None = None
    moving_time_seconds: int | None = None
    elapsed_time_seconds: int | None = None
    average_speed_mps: Decimal | None = None
    max_speed_mps: Decimal | None = None
    average_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None
    min_heart_rate_bpm: int | None = None
    average_cadence_spm: int | None = None
    max_cadence_spm: int | None = None
    elevation_gain_m: int | None = None
    elevation_loss_m: int | None = None
    calories_kcal: int | None = None
    average_stride_length_m: Decimal | None = None
    average_vertical_ratio_percent: Decimal | None = None
    average_vertical_oscillation_cm: Decimal | None = None
    average_ground_contact_time_ms: int | None = None
    ground_contact_balance_percent: Decimal | None = None
    average_running_power_w: int | None = None
    max_running_power_w: int | None = None
    garmin_primary_benefit: str | None = None
    garmin_aerobic_training_effect: Decimal | None = None
    garmin_anaerobic_training_effect: Decimal | None = None
    garmin_training_load: Decimal | None = None
    garmin_recovery_time_seconds: int | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    laps: list[ProviderLap] = field(default_factory=list)


@dataclass(slots=True)
class ProviderRecoverySnapshot:
    """Normalized provider result before it becomes a persisted canonical fact.

    Fields stay nullable: an unavailable Garmin metric is never converted to
    zero. Raw provider payloads deliberately do not cross this boundary.
    """

    recovery_date: date
    provider: str
    sleep_duration_minutes: int | None = None
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    sleep_score: int | None = None
    resting_heart_rate_bpm: int | None = None
    hrv_value: Decimal | None = None
    hrv_metric: str | None = None
    hrv_status: str | None = None
    average_stress: int | None = None
    max_stress: int | None = None
    body_battery_start: int | None = None
    body_battery_end: int | None = None
    body_battery_high: int | None = None
    body_battery_low: int | None = None
    respiration_rate: Decimal | None = None
    pulse_ox: Decimal | None = None
    provider_updated_at: datetime | None = None
    missing_fields: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class ActivityProvider(Protocol):
    connector_version: str

    def authenticate(self, username: str, password: str, region: str | None = None) -> ProviderAuthResult: ...

    def submit_mfa(self, mfa_token: str, mfa_code: str) -> ProviderAuthResult: ...

    def restore_session(self, token_payload: dict[str, Any]) -> None: ...

    def refresh_session(self) -> dict[str, Any] | None: ...

    def fetch_activities(self, start: datetime, end: datetime) -> list[ProviderActivity]: ...

    def fetch_activity_summary(self, external_activity_id: str) -> ProviderActivity: ...

    def fetch_activity_splits(self, external_activity_id: str) -> list[ProviderLap]: ...

    def fetch_activity_typed_splits(self, external_activity_id: str) -> list[ProviderLap]: ...

    def fetch_activity_split_summaries(self, external_activity_id: str) -> list[ProviderLap]: ...

    def fetch_activity_details(self, external_activity_id: str) -> ProviderActivity: ...

    def fetch_recovery(self, start: date, end: date) -> list[ProviderRecoverySnapshot]: ...

    def disconnect(self) -> None: ...

    def health_check(self) -> bool: ...
