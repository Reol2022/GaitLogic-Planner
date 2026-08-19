from __future__ import annotations

from server.integrations.activity_sync.capabilities import (
    ProviderCapabilities,
    ProviderDescriptor,
    RecoveryCapabilities,
)


def garmin_descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        key="garmin",
        display_name="Garmin",
        status="available",
        auth_flows=["password", "mfa"],
        capabilities=ProviderCapabilities(
            mfa=True,
            webhooks=False,
            # garminconnect 0.2.36 exposes these endpoint methods. Individual
            # watches, regions and dates may still return partial data.
            recovery=RecoveryCapabilities(
                sleep="SUPPORTED",
                resting_heart_rate="SUPPORTED",
                hrv="PARTIAL",
                stress="SUPPORTED",
                body_battery="PARTIAL",
                respiration="PARTIAL",
                pulse_ox="UNSUPPORTED",
            ),
        ),
        supported_sync_modes=["incremental", "initial_backfill", "recent_7d", "recent_30d", "custom_range"],
        notes="Garmin Connect 适配器，支持跑步活动同步、分段解析、计划匹配和自动导入。",
    )
