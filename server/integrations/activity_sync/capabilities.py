from __future__ import annotations

from pydantic import BaseModel, Field


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


class ProviderDescriptor(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    display_name: str
    status: str = "available"
    auth_flows: list[str] = Field(default_factory=list)
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    supported_sync_modes: list[str] = Field(default_factory=list)
    notes: str | None = None
