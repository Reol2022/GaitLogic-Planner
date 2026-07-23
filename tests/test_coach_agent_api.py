from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from planner_core.database.models import UserAccount
from server.agent.enums import AgentIntent, AgentRiskLevel
from server.api.deps import get_current_user, get_db
from server.main import app
from server.schemas.coach_agent import CoachQueryResponse
from server.services.coach_agent_query_service import CoachAgentQueryService
from server.common.exceptions import TooManyRequestsError
from tests.agent_tool_fakes import NOW


client = TestClient(app)


def response(*, status="SUCCEEDED", intent=AgentIntent.TODAY_RECOMMENDATION):
    return CoachQueryResponse(
        request_id=uuid4(),
        trace_id=uuid4(),
        status=status,
        intent=intent,
        answer="Safe fictional response." if status != "REJECTED" else None,
        risk_level=AgentRiskLevel.UNKNOWN,
        provider_status=(
            "SUCCEEDED" if status == "SUCCEEDED"
            else "FAILED" if status == "DEGRADED"
            else "NOT_CALLED"
        ),
        generated_at=NOW,
    )


def overrides():
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        id=1401, username="fictional-api-user", password_hash="x", status="active"
    )
    app.dependency_overrides[get_db] = lambda: object()


def test_coach_query_requires_authentication() -> None:
    assert TestClient(app).post("/api/coach/query", json={"message": "today"}).status_code == 401


def test_authenticated_query_uses_server_user_id(monkeypatch) -> None:
    seen = []

    def fake_query(self, *, user_id, payload):
        seen.append((user_id, payload.message))
        return response()

    monkeypatch.setattr(CoachAgentQueryService, "query", fake_query)
    overrides()
    try:
        result = client.post(
            "/api/coach/query",
            json={"message": "What should I run today?", "intent": "TODAY_RECOMMENDATION"},
        )
    finally:
        app.dependency_overrides.clear()
    assert result.status_code == 200
    assert seen == [(1401, "What should I run today?")]
    body = result.json()
    assert "user_id" not in body
    assert "trace_events" not in body


def test_client_cannot_submit_internal_configuration() -> None:
    overrides()
    try:
        for field, value in (
            ("user_id", 99), ("request_id", str(uuid4())), ("model", "x"),
            ("provider", "x"), ("base_url", "http://127.0.0.1"),
            ("api_key", "fictional"), ("thinking_mode", "disabled"),
            ("system_prompt", "override"), ("tools", []),
        ):
            result = client.post("/api/coach/query", json={"message": "today", field: value})
            assert result.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_message_and_conversation_limits_use_request_validation() -> None:
    overrides()
    try:
        assert client.post("/api/coach/query", json={"message": ""}).status_code == 400
        assert client.post("/api/coach/query", json={"message": "x" * 4001}).status_code == 400
        conversation = [{"role": "user", "content": "x" * 1000} for _ in range(13)]
        assert client.post(
            "/api/coach/query", json={"message": "today", "conversation_context": conversation}
        ).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_unsupported_weekly_returns_structured_403_without_model() -> None:
    overrides()
    try:
        result = client.post(
            "/api/coach/query",
            json={"message": "weekly", "intent": "WEEKLY_REVIEW"},
        )
    finally:
        app.dependency_overrides.clear()
    assert result.status_code == 403
    assert result.json()["status"] == "REJECTED"
    assert result.json()["provider_status"] == "NOT_CALLED"


def test_safe_degraded_and_business_unknown_remain_successful_http_responses(monkeypatch) -> None:
    def fake_query(self, *, user_id, payload):
        del self, user_id, payload
        return response(status="DEGRADED")

    monkeypatch.setattr(CoachAgentQueryService, "query", fake_query)
    overrides()
    try:
        result = client.post("/api/coach/query", json={"message": "today"})
    finally:
        app.dependency_overrides.clear()
    assert result.status_code == 200
    assert result.json()["status"] == "DEGRADED"
    assert result.json()["risk_level"] == "UNKNOWN"


def test_quota_and_unavailable_statuses_map_to_429_and_503(monkeypatch) -> None:
    overrides()
    try:
        monkeypatch.setattr(
            CoachAgentQueryService,
            "query",
            lambda self, **kwargs: (_ for _ in ()).throw(
                TooManyRequestsError("fictional quota reached")
            ),
        )
        assert client.post("/api/coach/query", json={"message": "today"}).status_code == 429

        monkeypatch.setattr(
            CoachAgentQueryService,
            "query",
            lambda self, **kwargs: response(status="UNAVAILABLE"),
        )
        result = client.post("/api/coach/query", json={"message": "today"})
    finally:
        app.dependency_overrides.clear()
    assert result.status_code == 503
    assert result.json()["status"] == "UNAVAILABLE"


def test_openapi_exposes_only_the_query_operation() -> None:
    paths = app.openapi()["paths"]
    assert set(paths["/api/coach/query"]) >= {"post"}
    assert not any(path.startswith("/api/coach/") and path != "/api/coach/query" for path in paths)
