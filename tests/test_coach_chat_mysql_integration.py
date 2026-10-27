"""Opt-in MySQL acceptance for the Coach Chat migration.

This test is deliberately skipped unless a caller supplies a dedicated local
database URL. It refuses remote hosts and non-test database names so a normal
test command can never touch a development or production database by mistake.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, insert, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.config import get_settings
from planner_core.database.models import AdminSystemSettings, CoachConversation, CoachMessage, UserAccount
from server.agent.enums import AgentIntent, AgentRiskLevel
from server.api.deps import get_db
from server.api.routes import coach as coach_routes
from server.common.exceptions import ConflictError
from server.main import app
from server.schemas.coach_agent import CoachQueryResponse
from server.schemas.coach_conversation import CoachConversationCreate, CoachConversationMessageCreate
from server.services.coach_conversation_service import CoachConversationService
from server.services.conversation_context_builder import ConversationContextBuilder
from scripts.upgrade_v0167_coach_context_summary import upgrade


TEST_DATABASE_URL = os.getenv("GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL")


def _validated_url():
    if not TEST_DATABASE_URL:
        pytest.skip("GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL is not configured")
    url = make_url(TEST_DATABASE_URL)
    if not url.drivername.startswith("mysql"):
        pytest.fail("Coach Chat MySQL acceptance requires a mysql+pymysql URL")
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Coach Chat MySQL acceptance refuses non-local database hosts")
    if not (url.database or "").startswith("gaitlogic_test_"):
        pytest.fail("Coach Chat MySQL acceptance requires a gaitlogic_test_* database")
    return url


def _reset_schema(engine) -> None:
    with engine.begin() as connection:
        CoachMessage.__table__.drop(connection, checkfirst=True)
        CoachConversation.__table__.drop(connection, checkfirst=True)
        AdminSystemSettings.__table__.drop(connection, checkfirst=True)
        UserAccount.__table__.drop(connection, checkfirst=True)
        UserAccount.__table__.create(connection, checkfirst=True)
        AdminSystemSettings.__table__.create(connection, checkfirst=True)
        upgrade(connection)
        upgrade(connection)  # The forward migration must be repeatable.


def _drop_schema(engine) -> None:
    with engine.begin() as connection:
        CoachMessage.__table__.drop(connection, checkfirst=True)
        CoachConversation.__table__.drop(connection, checkfirst=True)
        AdminSystemSettings.__table__.drop(connection, checkfirst=True)
        UserAccount.__table__.drop(connection, checkfirst=True)


@pytest.fixture
def mysql_engine():
    engine = create_engine(_validated_url(), future=True)
    _reset_schema(engine)
    try:
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


def _safe_response(answer: str = "Synthetic MySQL Coach answer.") -> CoachQueryResponse:
    return CoachQueryResponse(
        request_id=uuid4(),
        trace_id=uuid4(),
        status="SUCCEEDED",
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        answer=answer,
        summary="Synthetic MySQL summary.",
        risk_level=AgentRiskLevel.LOW,
        provider_status="SUCCEEDED",
        generated_at=datetime.now(timezone.utc),
    )


class _ImmediateCoach:
    def __init__(self, _db, *, tracer) -> None:
        self.tracer = tracer

    def query(self, *, user_id: int, payload):
        assert user_id > 0
        assert payload.message
        return _safe_response()


class _BlockingCoach:
    entered = Event()
    release = Event()

    def __init__(self, _db, *, tracer) -> None:
        self.tracer = tracer

    def query(self, *, user_id: int, payload):
        assert user_id > 0
        assert payload.message
        self.__class__.entered.set()
        assert self.__class__.release.wait(timeout=10), "test did not release the synthetic provider"
        return _safe_response("Delayed synthetic MySQL Coach answer.")


def _add_user(session: Session) -> int:
    row = UserAccount(username=f"coach-chat-mysql-{uuid4().hex[:12]}", password_hash="x", status="active")
    session.add(row)
    session.commit()
    return int(row.id)


def _service(session: Session, provider=_ImmediateCoach) -> CoachConversationService:
    return CoachConversationService(
        session,
        coach_service_factory=provider,
        context_builder=ConversationContextBuilder(max_messages=8, token_budget=800),
    )


class _HttpConversationService(CoachConversationService):
    """Keep the HTTP acceptance test offline while exercising its real routes."""

    def __init__(self, db, *, tracer=None) -> None:
        super().__init__(db, coach_service_factory=_ImmediateCoach, tracer=tracer)


def _register_and_login(client: TestClient, username: str) -> dict[str, str]:
    password = "coach-chat-test-password"
    registration = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "email": f"{username}@example.test",
            "nickname": username,
        },
    )
    assert registration.status_code == 200, registration.text
    login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.mysql_integration
def test_coach_chat_migration_is_idempotent_and_enforces_integrity(mysql_engine) -> None:
    with mysql_engine.begin() as connection:
        inspector = inspect(connection)
        columns = {item["name"] for item in inspector.get_columns("coach_conversations")}
        assert {
            "processing_turn_id",
            "processing_lease_id",
            "processing_started_at",
            "context_summary_json",
            "context_summary_version",
            "context_summary_through_sequence",
            "context_summary_updated_at",
            "context_summary_status",
            "context_summary_lease_id",
            "context_summary_started_at",
        } <= columns
        message_columns = {item["name"] for item in inspector.get_columns("coach_messages")}
        assert {
            "progress_stage",
            "progress_sequence",
            "progress_summary_json",
            "progress_updated_at",
        } <= message_columns
        indexes = {item["name"] for item in inspector.get_indexes("coach_messages")}
        assert "ix_coach_messages_conversation_sequence" in indexes
        foreign_keys = inspector.get_foreign_keys("coach_messages")
        assert any(item["referred_table"] == "coach_conversations" for item in foreign_keys)

        user_id = connection.execute(
            insert(UserAccount).values(
                username=f"coach-chat-mysql-{uuid4().hex[:12]}", password_hash="x", status="active"
            )
        ).inserted_primary_key[0]
        conversation_id = connection.execute(
            insert(CoachConversation).values(
                public_id=str(uuid4()), user_id=user_id, title="synthetic", status="active"
            )
        ).inserted_primary_key[0]
        connection.execute(
            insert(CoachMessage).values(
                public_id=str(uuid4()),
                conversation_id=conversation_id,
                role="user",
                content="synthetic message",
                status="completed",
                sequence_no=1,
                client_turn_id="mysql_turn_001",
            )
        )
        with connection.begin_nested():
            with pytest.raises(IntegrityError):
                connection.execute(
                    insert(CoachMessage).values(
                        public_id=str(uuid4()),
                        conversation_id=conversation_id,
                        role="user",
                        content="duplicate synthetic message",
                        status="completed",
                        sequence_no=2,
                        client_turn_id="mysql_turn_001",
                    )
                )

    # Run cascade verification in a fresh transaction after the deliberate
    # unique-constraint rollback above.
    with mysql_engine.begin() as connection:
        conversation_id = connection.scalar(select(CoachConversation.id).limit(1))
        assert conversation_id is not None
        connection.execute(delete(CoachConversation).where(CoachConversation.id == conversation_id))
        assert connection.scalar(select(func.count()).select_from(CoachMessage)) == 0


@pytest.mark.mysql_integration
def test_coach_chat_migration_upgrades_pre_progress_schema_idempotently(mysql_engine) -> None:
    """Older Coach tables gain progress and Context v2.1 columns without recreation."""
    progress_columns = (
        "progress_stage",
        "progress_sequence",
        "progress_summary_json",
        "progress_updated_at",
    )
    summary_columns = (
        "context_summary_json",
        "context_summary_version",
        "context_summary_through_sequence",
        "context_summary_updated_at",
        "context_summary_status",
        "context_summary_lease_id",
        "context_summary_started_at",
    )
    with mysql_engine.begin() as connection:
        for name in progress_columns:
            connection.execute(text(f"ALTER TABLE `coach_messages` DROP COLUMN `{name}`"))
        for name in summary_columns:
            connection.execute(text(f"ALTER TABLE `coach_conversations` DROP COLUMN `{name}`"))
        before = {item["name"] for item in inspect(connection).get_columns("coach_messages")}
        assert not set(progress_columns) & before
        before_summary = {
            item["name"] for item in inspect(connection).get_columns("coach_conversations")
        }
        assert not set(summary_columns) & before_summary
        upgrade(connection)
        upgrade(connection)
        after = {item["name"] for item in inspect(connection).get_columns("coach_messages")}
        assert set(progress_columns) <= after
        after_summary = {
            item["name"] for item in inspect(connection).get_columns("coach_conversations")
        }
        assert set(summary_columns) <= after_summary


@pytest.mark.mysql_integration
def test_mysql_http_lifecycle_authentication_and_user_isolation(mysql_engine, monkeypatch) -> None:
    """Exercise the real FastAPI routes and JWT dependency against local MySQL."""
    SessionLocal = sessionmaker(bind=mysql_engine, class_=Session)
    monkeypatch.setenv("JWT_SECRET_KEY", "coach-chat-local-mysql-http-test-secret")
    get_settings.cache_clear()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(coach_routes, "CoachConversationService", _HttpConversationService)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            suffix = uuid4().hex[:10]
            user_a_headers = _register_and_login(client, f"coach_http_a_{suffix}")
            user_b_headers = _register_and_login(client, f"coach_http_b_{suffix}")

            created = client.post("/api/coach/conversations", json={}, headers=user_a_headers)
            assert created.status_code == 201, created.text
            conversation_id = created.json()["id"]

            sent = client.post(
                f"/api/coach/conversations/{conversation_id}/messages",
                json={"client_turn_id": "mysql_http_turn_001", "message": "synthetic API request"},
                headers=user_a_headers,
            )
            assert sent.status_code == 200, sent.text
            assert sent.json()["status"] == "completed"
            assert sent.json()["response"]["answer"] == "Synthetic MySQL Coach answer."
            replay = client.post(
                f"/api/coach/conversations/{conversation_id}/messages",
                json={"client_turn_id": "mysql_http_turn_001", "message": "synthetic API request"},
                headers=user_a_headers,
            )
            assert replay.status_code == 200, replay.text

            history = client.get(
                f"/api/coach/conversations/{conversation_id}/messages?page=1&page_size=10",
                headers=user_a_headers,
            )
            assert history.status_code == 200, history.text
            assert [(item["role"], item["sequence_no"]) for item in history.json()["items"]] == [
                ("user", 1),
                ("assistant", 2),
            ]

            assert client.get(
                f"/api/coach/conversations/{conversation_id}", headers=user_b_headers
            ).status_code == 404
            assert client.get("/api/coach/conversations", headers=user_b_headers).json()["items"] == []

            archived = client.patch(
                f"/api/coach/conversations/{conversation_id}",
                json={"status": "archived", "title": "Local MySQL HTTP"},
                headers=user_a_headers,
            )
            assert archived.status_code == 200, archived.text
            assert archived.json()["status"] == "archived"
            assert client.post(
                f"/api/coach/conversations/{conversation_id}/messages",
                json={"client_turn_id": "mysql_http_turn_002", "message": "must be rejected"},
                headers=user_a_headers,
            ).status_code == 400
            assert client.delete(
                f"/api/coach/conversations/{conversation_id}", headers=user_a_headers
            ).status_code == 200
            assert client.get(
                f"/api/coach/conversations/{conversation_id}", headers=user_a_headers
            ).status_code == 404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.mark.mysql_integration
def test_mysql_serializes_duplicate_and_competing_conversation_turns(mysql_engine) -> None:
    SessionLocal = sessionmaker(bind=mysql_engine, class_=Session)
    setup_db = SessionLocal()
    try:
        user_id = _add_user(setup_db)
        conversation = _service(setup_db).create(user_id=user_id, payload=CoachConversationCreate())
    finally:
        setup_db.close()

    _BlockingCoach.entered.clear()
    _BlockingCoach.release.clear()
    first_payload = CoachConversationMessageCreate(client_turn_id="mysql_parallel_001", message="first synthetic request")
    second_payload = CoachConversationMessageCreate(client_turn_id="mysql_parallel_002", message="second synthetic request")

    def submit(payload):
        db = SessionLocal()
        try:
            return _service(db, _BlockingCoach).send_message(
                user_id=user_id, conversation_id=conversation.id, payload=payload
            )
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(submit, first_payload)
        assert _BlockingCoach.entered.wait(timeout=5), "first request did not reserve its MySQL lease"
        with pytest.raises(ConflictError):
            submit(first_payload)
        with pytest.raises(ConflictError):
            submit(second_payload)
        _BlockingCoach.release.set()
        assert first.result(timeout=10).status == "completed"

    verify_db = SessionLocal()
    try:
        messages = _service(verify_db).list_messages(
            user_id=user_id, conversation_id=conversation.id, page=1, page_size=20
        )
        assert [(item.role, item.sequence_no) for item in messages.items] == [("user", 1), ("assistant", 2)]
    finally:
        verify_db.close()


@pytest.mark.mysql_integration
def test_mysql_expired_lease_and_delete_reject_late_results(mysql_engine) -> None:
    SessionLocal = sessionmaker(bind=mysql_engine, class_=Session)
    setup_db = SessionLocal()
    try:
        user_id = _add_user(setup_db)
        service = _service(setup_db)
        conversation = service.create(user_id=user_id, payload=CoachConversationCreate())
        old_payload = CoachConversationMessageCreate(client_turn_id="mysql_old_lease", message="old request")
        _user, old_assistant, _replay, old_lease = service._reserve_turn(
            user_id=user_id, conversation_id=conversation.id, payload=old_payload
        )
        old_assistant_id = old_assistant.id
    finally:
        setup_db.close()

    stale_db = SessionLocal()
    try:
        row = stale_db.scalar(select(CoachConversation).where(CoachConversation.public_id == conversation.id))
        assert row is not None
        row.processing_started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        stale_db.commit()
        new_payload = CoachConversationMessageCreate(client_turn_id="mysql_new_lease", message="new request")
        _new_user, new_assistant, _replay, new_lease = _service(stale_db)._reserve_turn(
            user_id=user_id, conversation_id=conversation.id, payload=new_payload
        )
        new_assistant_id = new_assistant.id
    finally:
        stale_db.close()

    old_db = SessionLocal()
    try:
        assert _service(old_db)._complete_turn(
            assistant_message_id=old_assistant_id,
            client_turn_id=old_payload.client_turn_id,
            lease_id=old_lease,
            response=_safe_response("old late response"),
        ) is False
    finally:
        old_db.close()

    delete_db = SessionLocal()
    try:
        service = _service(delete_db)
        # Delete while the new lease is still pending, not after it completed.
        service.delete(user_id=user_id, conversation_id=conversation.id)
    finally:
        delete_db.close()

    late_db = SessionLocal()
    try:
        assert _service(late_db)._complete_turn(
            assistant_message_id=new_assistant_id,
            client_turn_id=new_payload.client_turn_id,
            lease_id=new_lease,
            response=_safe_response("deleted pending response"),
        ) is False
        assert late_db.scalar(select(CoachConversation).where(CoachConversation.public_id == conversation.id)) is None
        assert late_db.scalar(select(CoachMessage).where(CoachMessage.id == new_assistant_id)) is None
    finally:
        late_db.close()
