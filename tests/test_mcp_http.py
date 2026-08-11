"""Streamable HTTP MCP security tests using fictional identities and fake tools."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from planner_core.config import Settings, get_settings
from planner_core.database.models import UserAccount
from server.mcp.http import McpHttpDependencies, create_mcp_http_app
from server.observability.metrics import InMemoryMetricsSink, MetricsRecorder, MetricsTraceSink
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer
from server.services.auth_service import MCP_TOKEN_PURPOSE, _sign_jwt_payload, create_mcp_access_token
from tests.agent_tool_fakes import FakeDependencies


ALLOWED_ORIGIN = "https://mcp-client.example.test"


class _Session:
    def __init__(self, users: dict[int, UserAccount]) -> None:
        self.users = users
        self.rollback = Mock()
        self.close = Mock()

    def scalar(self, query):
        params = query.compile().params
        user_id = next(value for key, value in params.items() if key.startswith("id"))
        return self.users.get(user_id)


@pytest.fixture
def http_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "fictional-mcp-test-secret")
    get_settings.cache_clear()
    users = {
        101: UserAccount(id=101, username="fictional-a", password_hash="x", status="active"),
        202: UserAccount(id=202, username="fictional-b", password_hash="x", status="active"),
    }
    sessions: list[_Session] = []

    def session_factory() -> _Session:
        session = _Session(users)
        sessions.append(session)
        return session

    fake = FakeDependencies()
    settings = Settings(
        mcp_allowed_hosts="testserver",
        mcp_allowed_origins=ALLOWED_ORIGIN,
        mcp_http_enabled=True,
    )
    yield McpHttpDependencies(
        settings=settings,
        session_factory=session_factory,
        dependencies_factory=lambda _session: fake,
    ), users, fake, sessions
    get_settings.cache_clear()


def _token(user: UserAccount) -> str:
    return create_mcp_access_token(user)


def _headers(token: str | None, *, origin: str = ALLOWED_ORIGIN) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Origin": origin,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _initialize(client: TestClient, headers: dict[str, str]) -> dict[str, str]:
    response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "fictional-test-client", "version": "1"},
            },
        },
    )
    assert response.status_code == 200
    resolved = dict(headers)
    resolved["Mcp-Session-Id"] = response.headers["mcp-session-id"]
    resolved["MCP-Protocol-Version"] = "2025-06-18"
    return resolved


def _request(client: TestClient, headers: dict[str, str], method: str, params: dict) -> dict:
    response = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


def test_streamable_http_tools_list_and_authenticated_calls(http_dependencies) -> None:
    dependencies, users, fake, _sessions = http_dependencies
    with TestClient(create_mcp_http_app(dependencies=dependencies)) as client:
        headers = _initialize(client, _headers(_token(users[101])))
        listed = _request(client, headers, "tools/list", {})
        assert {item["name"] for item in listed["result"]["tools"]} == {
            "get_today_plan", "get_recent_training", "get_runner_state", "retrieve_training_knowledge"
        }
        for name, arguments in (
            ("get_today_plan", {}),
            ("get_recent_training", {"days": 7, "limit": 5}),
            ("get_runner_state", {}),
        ):
            result = _request(client, headers, "tools/call", {"name": name, "arguments": arguments})
            assert result["result"]["structuredContent"]["status"] == "SUCCEEDED"
    assert len(fake.seen_user_ids) >= 3
    assert set(fake.seen_user_ids) == {101}


@pytest.mark.parametrize("authorization, expected", [(None, "UNAUTHENTICATED"), ("Bearer bad.token.value", "INVALID_TOKEN")])
def test_http_mcp_rejects_missing_and_invalid_tokens(http_dependencies, authorization, expected) -> None:
    dependencies, _users, fake, _sessions = http_dependencies
    headers = _headers(None)
    if authorization:
        headers["Authorization"] = authorization
    with TestClient(create_mcp_http_app(dependencies=dependencies)) as client:
        response = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert response.status_code == 401
    assert response.json() == {"code": expected}
    assert fake.seen_user_ids == []


@pytest.mark.parametrize("claim, value, expected", [("exp", 0, "TOKEN_EXPIRED"), ("aud", "other-mcp", "INVALID_TOKEN")])
def test_http_mcp_rejects_expired_and_wrong_audience_tokens(http_dependencies, claim, value, expected) -> None:
    dependencies, users, fake, _sessions = http_dependencies
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(users[101].id),
        "iss": dependencies.settings.mcp_token_issuer,
        "aud": dependencies.settings.mcp_token_audience,
        "purpose": MCP_TOKEN_PURPOSE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    payload[claim] = value
    with TestClient(create_mcp_http_app(dependencies=dependencies)) as client:
        response = client.post("/mcp", headers=_headers(_sign_jwt_payload(payload)), json={})
    assert response.status_code == 401
    assert response.json() == {"code": expected}
    assert fake.seen_user_ids == []


def test_http_mcp_origin_rejection_happens_before_auth_or_tools(http_dependencies) -> None:
    dependencies, users, fake, sessions = http_dependencies
    with TestClient(create_mcp_http_app(dependencies=dependencies)) as client:
        response = client.post("/mcp", headers=_headers(_token(users[101]), origin="https://evil.example.test"), json={})
    assert response.status_code == 403
    assert response.json() == {"code": "INVALID_ORIGIN"}
    assert not sessions
    assert fake.seen_user_ids == []


def test_http_mcp_closed_world_arguments_cannot_override_identity(http_dependencies) -> None:
    dependencies, users, fake, _sessions = http_dependencies
    with TestClient(create_mcp_http_app(dependencies=dependencies)) as client:
        headers = _initialize(client, _headers(_token(users[101])))
        result = _request(
            client,
            headers,
            "tools/call",
            {"name": "get_recent_training", "arguments": {"days": 7, "user_id": 202}},
        )
    assert result["result"]["isError"] is True
    assert "INVALID_ARGUMENT" in result["result"]["content"][0]["text"]
    assert fake.seen_user_ids == []


def test_http_mcp_user_identity_is_server_validated_and_isolated(http_dependencies) -> None:
    dependencies, users, fake, _sessions = http_dependencies
    with TestClient(create_mcp_http_app(dependencies=dependencies)) as client:
        headers = _initialize(client, _headers(_token(users[202])))
        result = _request(client, headers, "tools/call", {"name": "get_runner_state", "arguments": {}})
    assert result["result"]["structuredContent"]["status"] == "SUCCEEDED"
    assert fake.seen_user_ids == [202]


def test_http_mcp_trace_metrics_and_sink_failures_are_non_blocking(http_dependencies) -> None:
    dependencies, users, fake, _sessions = http_dependencies
    trace_sink = InMemoryTraceSink()
    metric_sink = InMemoryMetricsSink()
    tracer = SafeTracer(FanoutTraceSink(trace_sink, MetricsTraceSink(MetricsRecorder(metric_sink))))
    enabled = McpHttpDependencies(
        settings=dependencies.settings,
        session_factory=dependencies.session_factory,
        dependencies_factory=dependencies.dependencies_factory,
        tracer=tracer,
    )
    with TestClient(create_mcp_http_app(dependencies=enabled)) as client:
        headers = _initialize(client, _headers(_token(users[101])))
        _request(client, headers, "tools/call", {"name": "get_today_plan", "arguments": {}})
    assert [(span.component, span.operation) for span in trace_sink.spans] == [
        ("auth", "validate"),
        ("mcp.http", "request"),
        ("auth", "validate"),
        ("tool", "invoke"),
        ("mcp", "tool"),
        ("mcp.http", "request"),
    ]
    tool_span = trace_sink.spans[3]
    assert tool_span.parent_span_id == trace_sink.spans[4].span_id
    assert metric_sink.counter("mcp_http_request_count") == 2
    assert metric_sink.counter("mcp_auth_success") == 2
    assert metric_sink.counter("mcp_tool_success") == 1
    assert all("user_id" not in str(span.metadata) and "token" not in str(span.metadata) for span in trace_sink.spans)
    assert fake.seen_user_ids == [101]


def test_http_trace_and_metrics_sink_failures_do_not_change_tool_result(http_dependencies) -> None:
    class BrokenTraceSink:
        def write(self, _span) -> None:
            raise RuntimeError("fictional trace outage")

    class BrokenMetricsSink:
        def record(self, _point) -> None:
            raise RuntimeError("fictional metrics outage")

    dependencies, users, fake, _sessions = http_dependencies
    tracer = SafeTracer(
        FanoutTraceSink(BrokenTraceSink(), MetricsTraceSink(MetricsRecorder(BrokenMetricsSink())))
    )
    broken = McpHttpDependencies(
        settings=dependencies.settings,
        session_factory=dependencies.session_factory,
        dependencies_factory=dependencies.dependencies_factory,
        tracer=tracer,
    )
    with TestClient(create_mcp_http_app(dependencies=broken)) as client:
        headers = _initialize(client, _headers(_token(users[101])))
        result = _request(client, headers, "tools/call", {"name": "get_runner_state", "arguments": {}})
    assert result["result"]["structuredContent"]["status"] == "SUCCEEDED"
    assert fake.seen_user_ids == [101]


def test_http_tracing_and_metrics_can_be_disabled_without_changing_result(http_dependencies) -> None:
    dependencies, users, fake, _sessions = http_dependencies
    disabled = McpHttpDependencies(
        settings=dependencies.settings,
        session_factory=dependencies.session_factory,
        dependencies_factory=dependencies.dependencies_factory,
        tracer=SafeTracer(enabled=False),
    )
    with TestClient(create_mcp_http_app(dependencies=disabled)) as client:
        headers = _initialize(client, _headers(_token(users[101])))
        result = _request(client, headers, "tools/call", {"name": "get_recent_training", "arguments": {}})
    assert result["result"]["structuredContent"]["status"] == "SUCCEEDED"
    assert fake.seen_user_ids and set(fake.seen_user_ids) == {101}


def test_stdio_remains_unauthenticated_and_http_never_uses_provider(http_dependencies) -> None:
    """Regression guard: HTTP uses the local fake registry and no Provider gateway."""

    dependencies, users, fake, _sessions = http_dependencies
    with TestClient(create_mcp_http_app(dependencies=dependencies)) as client:
        headers = _initialize(client, _headers(_token(users[101])))
        _request(client, headers, "tools/call", {"name": "get_today_plan", "arguments": {}})
    assert fake.seen_user_ids == [101]
    assert "provider" not in str(fake).lower()


def test_main_mounts_remote_mcp_only_when_explicitly_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "fictional-main-mcp-secret")
    monkeypatch.setenv("MCP_HTTP_ENABLED", "true")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", ALLOWED_ORIGIN)
    get_settings.cache_clear()
    from server.main import create_app

    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        response = client.post("/mcp", headers={"Origin": ALLOWED_ORIGIN}, json={})
    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
    get_settings.cache_clear()
