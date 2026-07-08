from __future__ import annotations

from dataclasses import dataclass, field

from planner_core.config import get_settings
from server.integrations.activity_sync.capabilities import ProviderDescriptor
from server.integrations.activity_sync.exceptions import ProviderNotFoundError
from server.integrations.activity_sync.providers.base import ActivityProviderAdapter
from server.integrations.activity_sync.providers.garmin import GarminProviderAdapter
from server.integrations.activity_sync.providers.mock import MockProviderAdapter


@dataclass
class ProviderRegistry:
    _providers: dict[str, ActivityProviderAdapter] = field(default_factory=dict)

    def register(self, provider: ActivityProviderAdapter) -> None:
        key = provider.provider_key.strip().lower()
        if key in self._providers:
            raise ValueError(f"Provider already registered: {key}")
        self._providers[key] = provider

    def get(self, provider_key: str) -> ActivityProviderAdapter:
        key = provider_key.strip().lower()
        provider = self._providers.get(key)
        if provider is None:
            raise ProviderNotFoundError(key)
        return provider

    def list_descriptors(self) -> list[ProviderDescriptor]:
        return [provider.descriptor() for provider in self._providers.values()]


_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        registry = ProviderRegistry()
        registry.register(GarminProviderAdapter())
        registry.register(MockProviderAdapter(enabled=get_settings().data_sync_mock_provider_enabled))
        _registry = registry
    return _registry
