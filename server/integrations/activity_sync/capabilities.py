from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CapabilityStatus = Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED", "NOT_VERIFIED"]


class RecoveryCapabilities(BaseModel):
    """Provider-declared health-data capabilities, not user-data availability."""

    sleep: CapabilityStatus = "UNSUPPORTED"
    resting_heart_rate: CapabilityStatus = "UNSUPPORTED"
    hrv: CapabilityStatus = "UNSUPPORTED"
    stress: CapabilityStatus = "UNSUPPORTED"
    body_battery: CapabilityStatus = "UNSUPPORTED"
    respiration: CapabilityStatus = "UNSUPPORTED"
    pulse_ox: CapabilityStatus = "UNSUPPORTED"


class ProviderCapabilities(BaseModel):
    connect: bool = True
    disconnect: bool = True
    mfa: bool = False
    manual_sync: bool = True
    incremental_sync: bool = True
    initial_backfill: bool = True
    custom_range_sync: bool = True
    activity_reprocess: bool = True
    activity_ignore: bool = True
    activity_restore: bool = True
    auto_import_setting: bool = True
    webhooks: bool = False
    recovery: RecoveryCapabilities = Field(default_factory=RecoveryCapabilities)


class ProviderDescriptor(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    display_name: str
    status: str = "available"
    auth_flows: list[str] = Field(default_factory=list)
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    supported_sync_modes: list[str] = Field(default_factory=list)
    notes: str | None = None
