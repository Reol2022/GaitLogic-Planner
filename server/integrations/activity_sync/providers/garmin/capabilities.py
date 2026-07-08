from __future__ import annotations

from server.integrations.activity_sync.capabilities import ProviderCapabilities, ProviderDescriptor


def garmin_descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        key="garmin",
        display_name="Garmin",
        status="available",
        auth_flows=["password", "mfa"],
        capabilities=ProviderCapabilities(mfa=True, webhooks=False),
        supported_sync_modes=["incremental", "initial_backfill", "recent_7d", "recent_30d", "custom_range"],
        notes="Garmin Connect 适配器，支持跑步活动同步、分段解析、计划匹配和自动导入。",
    )
