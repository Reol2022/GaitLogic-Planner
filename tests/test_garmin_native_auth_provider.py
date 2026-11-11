from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from server.integrations.activity_provider.base import ProviderError
from server.integrations.activity_provider.garmin import (
    GARMIN_API_TIMEOUT_SECONDS,
    GARTH_TIMEOUT_SECONDS,
    GARTH_TOKEN_FORMAT,
    MFA_STATE_CACHE,
    GarminActivityProvider,
)


class FakeGarthClient:
    def __init__(self) -> None:
        self.timeout = 10
        self.loaded_tokenstore: str | None = None

    def dumps(self) -> str:
        return "fictional-garth-tokenstore"


class FakeGarmin:
    login_result: tuple[object, object] = ("access", "refresh")
    activity_pages: dict[int, list[dict]] = {}
    instances: list["FakeGarmin"] = []
    split_calls: list[str] = []

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        *,
        is_cn: bool = False,
        return_on_mfa: bool = False,
    ) -> None:
        self.email = email
        self.password = password
        self.is_cn = is_cn
        self.return_on_mfa = return_on_mfa
        self.garth = FakeGarthClient()
        self.instances.append(self)

    def login(self, tokenstore: str | None = None):
        self.garth.loaded_tokenstore = tokenstore
        return self.login_result

    def get_activities(self, start: int, limit: int, activitytype: str | None = None):
        assert limit == 100
        assert activitytype is None
        return self.activity_pages.get(start, [])

    def get_activity_splits(self, external_activity_id: str):
        self.split_calls.append(external_activity_id)
        return []


@pytest.fixture(autouse=True)
def garth_garmin(monkeypatch: pytest.MonkeyPatch):
    FakeGarmin.login_result = ("access", "refresh")
    FakeGarmin.activity_pages = {}
    FakeGarmin.instances.clear()
    FakeGarmin.split_calls.clear()
    MFA_STATE_CACHE.clear()
    monkeypatch.setitem(sys.modules, "garminconnect", SimpleNamespace(Garmin=FakeGarmin))
    yield
    MFA_STATE_CACHE.clear()


def test_cn_login_persists_garth_tokenstore() -> None:
    result = GarminActivityProvider().authenticate("runner@example.test", "fictional", "cn")

    assert result.status == "connected"
    assert result.token_payload == {
        "token_format": GARTH_TOKEN_FORMAT,
        "tokenstore": "fictional-garth-tokenstore",
        "region": "cn",
    }
    client = FakeGarmin.instances[0]
    assert client.is_cn is True
    assert client.return_on_mfa is True
    assert client.garth.timeout == GARTH_TIMEOUT_SECONDS


def test_restore_session_uses_encrypted_garth_tokenstore() -> None:
    provider = GarminActivityProvider()
    payload = {
        "token_format": GARTH_TOKEN_FORMAT,
        "tokenstore": "fictional-garth-tokenstore",
        "region": "cn",
    }

    provider.restore_session(payload)

    client = FakeGarmin.instances[0]
    assert client.is_cn is True
    assert client.garth.loaded_tokenstore == payload["tokenstore"]
    assert provider.refresh_session() == payload


def test_native_di_payload_requires_fresh_login_after_downgrade() -> None:
    provider = GarminActivityProvider()

    with pytest.raises(ProviderError) as exc_info:
        provider.restore_session({"token_format": "garminconnect_native_di_v1", "tokenstore": "{}", "region": "cn"})

    assert exc_info.value.code == "REAUTHENTICATION_REQUIRED"


def test_fetch_activities_uses_working_paginated_api_and_date_filter() -> None:
    FakeGarmin.activity_pages = {
        0: [
            {"activityId": 3, "startTimeLocal": "2026-08-24 08:00:00", "activityType": {"typeKey": "running"}},
            {"activityId": 99, "startTimeLocal": "2026-08-22 08:00:00", "activityType": {"typeKey": "cycling"}},
            {"activityId": 2, "startTimeLocal": "2026-08-20 08:00:00", "activityType": {"typeKey": "running"}},
            {"activityId": 1, "startTimeLocal": "2026-08-01 08:00:00", "activityType": {"typeKey": "running"}},
        ]
    }
    provider = GarminActivityProvider()
    provider.authenticate("runner@example.test", "fictional", "cn")

    rows = provider.fetch_activities(datetime(2026, 8, 15), datetime(2026, 8, 23, 23, 59, 59))

    assert [row.external_activity_id for row in rows] == ["2"]
    assert FakeGarmin.split_calls == []
    assert FakeGarmin.instances[0].garth.timeout == GARMIN_API_TIMEOUT_SECONDS


@pytest.mark.parametrize("utc_value", ["2026-11-10 11:00:00", "2026-11-10T11:00:00Z", "2026-11-10T19:00:00+08:00"])
def test_evening_activity_is_filtered_by_utc_not_local_wall_clock(utc_value):
    FakeGarmin.activity_pages = {0: [{
        "activityId": "synthetic-evening", "startTimeLocal": "2026-11-10 19:00:00",
        "startTimeGMT": utc_value, "activityType": {"typeKey": "running"},
    }]}
    provider = GarminActivityProvider()
    provider.authenticate("runner@example.test", "fictional", "cn")
    rows = provider.fetch_activities(datetime(2026, 11, 10, 10), datetime(2026, 11, 10, 13))
    assert [r.external_activity_id for r in rows] == ["synthetic-evening"]
    assert rows[0].start_time_local == datetime(2026, 11, 10, 19)
    assert rows[0].start_time_utc == datetime(2026, 11, 10, 11)
    assert FakeGarmin.split_calls == []


@pytest.mark.parametrize("zone", ["Asia/Shanghai", {"timeZone": "Asia/Shanghai"}, {"unitKey": "Asia/Shanghai"}])
def test_missing_gmt_uses_activity_timezone_instead_of_server_timezone(zone):
    FakeGarmin.activity_pages = {0: [{
        "activityId": "synthetic-fallback", "startTimeLocal": "2026-11-10 19:00:00",
        "timeZoneUnitDTO": zone, "activityType": {"typeKey": "running"},
    }]}
    provider = GarminActivityProvider()
    provider.authenticate("runner@example.test", "fictional", "cn")
    rows = provider.fetch_activities(datetime(2026, 11, 10, 10), datetime(2026, 11, 10, 13))
    assert [r.external_activity_id for r in rows] == ["synthetic-fallback"]
    assert rows[0].timezone == "Asia/Shanghai"


def test_utc_window_boundaries_cross_midnight_and_exclude_outside_activities():
    FakeGarmin.activity_pages = {0: [
        {"activityId": str(i), "startTimeLocal": local, "startTimeGMT": utc,
         "activityType": {"typeKey": "running"}}
        for i, local, utc in [
            (4, "2026-11-11 08:00:01", "2026-11-11 00:00:01"),
            (3, "2026-11-11 08:00:00", "2026-11-11 00:00:00"),
            (2, "2026-11-11 00:30:00", "2026-11-10 16:30:00"),
            (1, "2026-11-11 00:29:59", "2026-11-10 16:29:59"),
        ]
    ]}
    provider = GarminActivityProvider()
    provider.authenticate("runner@example.test", "fictional", "cn")
    # Offset-aware ranges must represent the same instants as naive UTC jobs.
    local_zone = timezone(timedelta(hours=8))
    rows = provider.fetch_activities(datetime(2026, 11, 11, 0, 30, tzinfo=local_zone),
                                     datetime(2026, 11, 11, 8, tzinfo=local_zone))
    assert [r.external_activity_id for r in rows] == ["3", "2"]


def test_negative_offset_activity_uses_gmt_and_unknown_zone_does_not_guess():
    FakeGarmin.activity_pages = {0: [
        {"activityId": "valid", "startTimeLocal": "2026-11-10 06:00:00",
         "startTimeGMT": "2026-11-10T14:00:00Z", "timeZoneId": "America/Los_Angeles",
         "activityType": {"typeKey": "running"}},
        {"activityId": "invalid", "startTimeLocal": "2026-11-10 06:00:00",
         "timeZoneId": "Not/A_Zone", "activityType": {"typeKey": "running"}},
    ]}
    provider = GarminActivityProvider()
    provider.authenticate("runner@example.test", "fictional", "cn")
    rows = provider.fetch_activities(datetime(2026, 11, 10, 13), datetime(2026, 11, 10, 15))
    assert [r.external_activity_id for r in rows] == ["valid"]
