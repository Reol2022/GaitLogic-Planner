from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from server.integrations.activity_provider.base import ProviderActivity, ProviderAuthResult
from server.integrations.activity_sync.capabilities import ProviderDescriptor
from server.integrations.activity_sync.exceptions import ProviderCapabilityNotSupportedError


class ActivityProviderAdapter(ABC):
    provider_key: str

    @abstractmethod
    def descriptor(self) -> ProviderDescriptor:
        raise NotImplementedError

    def begin_connection(self, username: str, password: str, region: str | None = None) -> ProviderAuthResult:
        raise ProviderCapabilityNotSupportedError("connect")

    def continue_connection(self, mfa_token: str, mfa_code: str) -> ProviderAuthResult:
        raise ProviderCapabilityNotSupportedError("mfa")

    def restore_session(self, token_payload: dict) -> None:
        raise ProviderCapabilityNotSupportedError("restore_session")

    def refresh_session(self) -> dict | None:
        return None

    def fetch_activities(self, start: datetime, end: datetime) -> list[ProviderActivity]:
        raise ProviderCapabilityNotSupportedError("manual_sync")

    def sanitize_payload(self, payload: dict) -> dict:
        return dict(payload)

    def normalize_activity(self, payload: dict) -> ProviderActivity:
        raise ProviderCapabilityNotSupportedError("normalize_activity")

    def health_check(self) -> bool:
        return True
