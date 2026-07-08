from __future__ import annotations

from datetime import datetime

from server.integrations.activity_provider import GarminActivityProvider, ProviderActivity, ProviderAuthResult
from server.integrations.activity_sync.capabilities import ProviderDescriptor
from server.integrations.activity_sync.providers.base import ActivityProviderAdapter
from server.integrations.activity_sync.providers.garmin.capabilities import garmin_descriptor
from server.integrations.activity_sync.providers.garmin.sanitizer import sanitize_garmin_payload


class GarminProviderAdapter(ActivityProviderAdapter):
    provider_key = "garmin"

    def __init__(self) -> None:
        self._provider = GarminActivityProvider()

    @property
    def connector_version(self) -> str:
        return self._provider.connector_version

    def descriptor(self) -> ProviderDescriptor:
        return garmin_descriptor()

    def begin_connection(self, username: str, password: str, region: str | None = None) -> ProviderAuthResult:
        return self._provider.authenticate(username, password, region)

    def continue_connection(self, mfa_token: str, mfa_code: str) -> ProviderAuthResult:
        return self._provider.submit_mfa(mfa_token, mfa_code)

    def restore_session(self, token_payload: dict) -> None:
        self._provider.restore_session(token_payload)

    def refresh_session(self) -> dict | None:
        return self._provider.refresh_session()

    def fetch_activities(self, start: datetime, end: datetime) -> list[ProviderActivity]:
        return self._provider.fetch_activities(start, end)

    def sanitize_payload(self, payload: dict) -> dict:
        return sanitize_garmin_payload(payload)

    def health_check(self) -> bool:
        return self._provider.health_check()
