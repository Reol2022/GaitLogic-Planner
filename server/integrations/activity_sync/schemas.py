from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from server.integrations.activity_sync.capabilities import ProviderCapabilities, ProviderDescriptor
from server.schemas.garmin_sync import ExternalActivityRead, ExternalSyncJobRead


class DataSyncConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    connected: bool
    connection_id: int | None = None
    provider: str
    status: str = "disconnected"
    region: str | None = None
    masked_account_identifier: str | None = None
    auto_import_enabled: bool = True
    auto_sync_enabled: bool = False
    auto_sync_last_run_at: datetime | None = None
    last_authenticated_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    last_error_code: str | None = None
    last_error_at: datetime | None = None
    descriptor: ProviderDescriptor | None = None


class DataSyncConnectRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    region: str | None = Field(default=None, max_length=32)
    options: dict[str, Any] | None = None


class DataSyncChallengeRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=512)
    mfa_code: str = Field(min_length=1, max_length=32)


class DataSyncConnectResponse(BaseModel):
    status: str
    connection: DataSyncConnectionRead | None = None
    mfa_token: str | None = None
    safe_message: str | None = None


class DataSyncRequest(BaseModel):
    sync_mode: str = "incremental"
    start: datetime | None = None
    end: datetime | None = None


class DataSyncActivityActionRequest(BaseModel):
    action: str | None = None
    workout_log_id: int | None = None
    planned_workout_id: int | None = None
    reason: str | None = Field(default=None, max_length=255)


class ProviderListResponse(BaseModel):
    providers: list[ProviderDescriptor]


class DataSyncJobListResponse(BaseModel):
    jobs: list[ExternalSyncJobRead]


class DataSyncActivityListResponse(BaseModel):
    activities: list[ExternalActivityRead]


__all__ = [
    "DataSyncActivityActionRequest",
    "DataSyncActivityListResponse",
    "DataSyncChallengeRequest",
    "DataSyncConnectRequest",
    "DataSyncConnectResponse",
    "DataSyncConnectionRead",
    "DataSyncJobListResponse",
    "DataSyncRequest",
    "ExternalActivityRead",
    "ExternalSyncJobRead",
    "ProviderCapabilities",
    "ProviderDescriptor",
    "ProviderListResponse",
]
