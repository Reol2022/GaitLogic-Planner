from __future__ import annotations

import sys
from datetime import datetime
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
