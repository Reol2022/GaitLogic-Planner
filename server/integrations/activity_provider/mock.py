from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from server.integrations.activity_provider.base import ProviderActivity, ProviderAuthResult, ProviderLap


class MockActivityProvider:
    connector_version = "mock-garmin-provider-v1"

    def __init__(self) -> None:
        self._token_payload: dict[str, Any] | None = None

    def authenticate(self, username: str, password: str, region: str | None = None) -> ProviderAuthResult:
        return ProviderAuthResult(
            status="connected",
            token_payload={"mock_user": username, "region": region or "cn", "session": "mock-session"},
            account_identifier=username,
            masked_account_identifier=_mask_account(username),
            provider_user_id=f"mock-{abs(hash(username))}",
        )

    def submit_mfa(self, mfa_token: str, mfa_code: str) -> ProviderAuthResult:
        return ProviderAuthResult(status="connected", token_payload={"mfa": "ok", "session": mfa_token})

    def restore_session(self, token_payload: dict[str, Any]) -> None:
        self._token_payload = dict(token_payload)

    def refresh_session(self) -> dict[str, Any] | None:
        return self._token_payload

    def fetch_activities(self, start: datetime, end: datetime) -> list[ProviderActivity]:
        anchor = max(start, end - timedelta(days=2))
        return [
            ProviderActivity(
                external_activity_id=f"mock-{anchor.date().isoformat()}-easy",
                activity_name="Mock Easy Run",
                activity_type="outdoor_running",
                activity_subtype="running",
                start_time_local=anchor.replace(hour=7, minute=30, second=0, microsecond=0),
                timezone="Asia/Shanghai",
                distance_m=Decimal("10240"),
                duration_seconds=2780,
                timer_time_seconds=2780,
                moving_time_seconds=2740,
                elapsed_time_seconds=2805,
                average_speed_mps=Decimal("3.683"),
                average_heart_rate_bpm=142,
                max_heart_rate_bpm=165,
                average_cadence_spm=176,
                elevation_gain_m=38,
                calories_kcal=650,
                raw_payload={"activityId": "mock-easy", "activityType": "running"},
                laps=[
                    ProviderLap(lap_index=1, distance_m=Decimal("5120"), duration_seconds=1390, segment_role="easy"),
                    ProviderLap(lap_index=2, distance_m=Decimal("5120"), duration_seconds=1390, segment_role="easy"),
                ],
            )
        ]

    def fetch_activity_summary(self, external_activity_id: str) -> ProviderActivity:
        return self.fetch_activities(datetime.utcnow() - timedelta(days=1), datetime.utcnow())[0]

    def fetch_activity_splits(self, external_activity_id: str) -> list[ProviderLap]:
        return self.fetch_activity_summary(external_activity_id).laps

    def fetch_activity_typed_splits(self, external_activity_id: str) -> list[ProviderLap]:
        return self.fetch_activity_splits(external_activity_id)

    def fetch_activity_split_summaries(self, external_activity_id: str) -> list[ProviderLap]:
        return self.fetch_activity_splits(external_activity_id)

    def fetch_activity_details(self, external_activity_id: str) -> ProviderActivity:
        return self.fetch_activity_summary(external_activity_id)

    def disconnect(self) -> None:
        self._token_payload = None

    def health_check(self) -> bool:
        return True


def _mask_account(account: str) -> str:
    if "@" in account:
        name, domain = account.split("@", 1)
        return f"{name[:2]}****@{domain}"
    return f"{account[:2]}****"
