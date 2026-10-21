from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, DefaultClause, create_engine, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from planner_core.database.base import Base
from planner_core.database.models import UserAccount
from server.agent.enums import AgentIntent, AgentRiskLevel
from server.api.deps import get_current_user, get_db
from server.api.routes import coach as coach_routes
from server.main import app
from server.schemas.coach_agent import CoachQueryResponse
from server.services.coach_conversation_service import CoachConversationService


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


class _FakeCoach:
    contexts: list[list[tuple[str, str]]] = []

    def __init__(self, _db, *, tracer) -> None:
        self.tracer = tracer

    def query(self, *, user_id: int, payload):
        assert user_id in {1, 2}
        self.__class__.contexts.append([(item.role, item.content) for item in payload.conversation_context])
        return CoachQueryResponse(
            request_id=uuid4(),
            trace_id=uuid4(),
            status="SUCCEEDED",
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
            answer="Synthetic safe Coach answer.",
            summary="Synthetic summary.",
            risk_level=AgentRiskLevel.LOW,
            provider_status="SUCCEEDED",
            generated_at=datetime.now(timezone.utc),
        )


class _ConversationServiceUnderTest(CoachConversationService):
    def __init__(self, db, *, tracer=None) -> None:
        super().__init__(db, coach_service_factory=_FakeCoach, tracer=tracer)


@pytest.fixture
def conversation_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    mysql_only_defaults = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.server_default is not None and "ON UPDATE" in str(column.server_default.arg):
                mysql_only_defaults.append((column, column.server_default))
                column.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
    try:
        Base.metadata.create_all(engine)
    finally:
        for column, default in mysql_only_defaults:
            column.server_default = default
    session = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()
    session.add_all(
        [
            UserAccount(id=1, username="fictional-conversation-a", password_hash="x", status="active"),
            UserAccount(id=2, username="fictional-conversation-b", password_hash="x", status="active"),
        ]
    )
    session.commit()
    identity = {"user_id": 1}

    def override_get_db():
        yield session

    def override_current_user():
        return session.get(UserAccount, identity["user_id"])

    _FakeCoach.contexts = []
    monkeypatch.setattr(coach_routes, "CoachConversationService", _ConversationServiceUnderTest)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        with TestClient(app) as client:
            yield client, identity
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def _create_conversation(client: TestClient) -> str:
    result = client.post("/api/coach/conversations", json={})
    assert result.status_code == 201, result.text
    return result.json()["id"]


def _send(client: TestClient, conversation_id: str, turn_id: str, message: str):
    return client.post(
        f"/api/coach/conversations/{conversation_id}/messages",
        json={"client_turn_id": turn_id, "message": message},
    )


def test_conversation_api_persists_orders_pages_and_manages_lifecycle(conversation_client) -> None:
    client, _identity = conversation_client
    conversation_id = _create_conversation(client)
    assert _send(client, conversation_id, "api_turn_0001", "第一条合成问题").status_code == 200
    assert _send(client, conversation_id, "api_turn_0002", "第二条合成问题").status_code == 200

    first_page = client.get(f"/api/coach/conversations/{conversation_id}/messages?page=1&page_size=2")
    second_page = client.get(f"/api/coach/conversations/{conversation_id}/messages?page=2&page_size=2")
    assert first_page.status_code == second_page.status_code == 200
    assert [item["sequence_no"] for item in first_page.json()["items"]] == [3, 4]
    assert [item["sequence_no"] for item in second_page.json()["items"]] == [1, 2]
    assert first_page.json()["total"] == second_page.json()["total"] == 4
    assert _FakeCoach.contexts[0] == []
    assert _FakeCoach.contexts[1] == [
        ("user", "第一条合成问题"),
        ("assistant", "Synthetic safe Coach answer."),
    ]

    renamed = client.patch(f"/api/coach/conversations/{conversation_id}", json={"title": "API 联调会话"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "API 联调会话"
    archived = client.patch(f"/api/coach/conversations/{conversation_id}", json={"status": "archived"})
    assert archived.status_code == 200
    assert _send(client, conversation_id, "api_turn_0003", "不能发送").status_code == 400
    assert client.delete(f"/api/coach/conversations/{conversation_id}").status_code == 200
    assert client.get(f"/api/coach/conversations/{conversation_id}").status_code == 404


def test_conversation_api_is_user_scoped_and_idempotent(conversation_client) -> None:
    client, identity = conversation_client
    conversation_id = _create_conversation(client)
    original = _send(client, conversation_id, "api_replay_01", "幂等合成问题")
    replay = _send(client, conversation_id, "api_replay_01", "幂等合成问题")
    assert original.status_code == replay.status_code == 200
    messages = client.get(f"/api/coach/conversations/{conversation_id}/messages")
    assert messages.status_code == 200
    assert messages.json()["total"] == 2

    identity["user_id"] = 2
    assert client.get(f"/api/coach/conversations/{conversation_id}").status_code == 404
    assert client.patch(f"/api/coach/conversations/{conversation_id}", json={"title": "forbidden"}).status_code == 404
    assert client.delete(f"/api/coach/conversations/{conversation_id}").status_code == 404
    assert client.get("/api/coach/conversations").json()["items"] == []
