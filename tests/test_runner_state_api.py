from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.main import app
from server.services.runner_state_service import RunnerStateService, build_runner_state_snapshot


def _empty_snapshot(runner_id: int):
    return build_runner_state_snapshot(
        runner_id=runner_id,
        cycle=None,
        log_rows=[],
        planned_workouts=[],
        generated_at=datetime(2026, 7, 15, 12, tzinfo=ZoneInfo("Asia/Shanghai")),
        timezone_name="Asia/Shanghai",
        calculation_window_end=date(2026, 7, 15),
    )


def test_runner_state_route_requires_authentication():
    response = TestClient(app).get("/api/runner-state/current")
    assert response.status_code == 401


def test_runner_state_route_uses_current_user_and_exposes_no_sensitive_fields(monkeypatch):
    current_user = UserAccount(
        id=71,
        username="fictional-runner",
        email="private@example.invalid",
        password_hash="not-a-real-hash",
        status="active",
    )
    seen: list[int] = []

    def fake_get_current(self, user, *, generated_at=None):
        seen.append(user.id)
        return _empty_snapshot(user.id)

    monkeypatch.setattr(RunnerStateService, "get_current", fake_get_current)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    try:
        response = TestClient(app).get("/api/runner-state/current?user_id=999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert seen == [71]
    payload = response.json()
    assert payload["snapshot"]["identity"]["runner_id"] == 71
    serialized = str(payload).lower()
    for sensitive in ("email", "password", "garmin", "access_token", "refresh_token"):
        assert sensitive not in serialized
    assert payload["snapshot"]["inferred_state"]["fitness_state"] == "UNKNOWN"


def test_runner_state_service_error_uses_standard_error_response(monkeypatch):
    current_user = UserAccount(id=72, username="runner", password_hash="x", status="active")

    def fail(self, user, *, generated_at=None):
        raise RuntimeError("internal detail must not leak")

    monkeypatch.setattr(RunnerStateService, "get_current", fail)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/api/runner-state/current")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_SERVER_ERROR"
    assert "internal detail" not in response.text
