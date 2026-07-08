from __future__ import annotations

from datetime import datetime

from server.integrations.activity_provider import MockActivityProvider, ProviderActivity, ProviderAuthResult
from server.integrations.activity_sync.capabilities import ProviderCapabilities, ProviderDescriptor
from server.integrations.activity_sync.exceptions import ProviderUnavailableError
from server.integrations.activity_sync.providers.base import ActivityProviderAdapter


class MockProviderAdapter(ActivityProviderAdapter):
    provider_key = "mock"

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._provider = MockActivityProvider()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            key="mock",
            display_name="Mock Provider",
            status="available" if self.enabled else "disabled_in_production",
            auth_flows=["password"],
            capabilities=ProviderCapabilities(mfa=False),
            supported_sync_modes=["incremental", "initial_backfill", "recent_7d", "recent_30d", "custom_range"],
            notes="用于开发和自动化测试的模拟运动数据平台。",
        )

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise ProviderUnavailableError("Mock 同步平台仅用于开发环境，当前未开放。", error_code="PROVIDER_DISABLED")

    def begin_connection(self, username: str, password: str, region: str | None = None) -> ProviderAuthResult:
        self._require_enabled()
        return self._provider.authenticate(username, password, region)

    def restore_session(self, token_payload: dict) -> None:
        self._require_enabled()
        self._provider.restore_session(token_payload)

    def refresh_session(self) -> dict | None:
        return self._provider.refresh_session()

    def fetch_activities(self, start: datetime, end: datetime) -> list[ProviderActivity]:
        self._require_enabled()
        return self._provider.fetch_activities(start, end)
