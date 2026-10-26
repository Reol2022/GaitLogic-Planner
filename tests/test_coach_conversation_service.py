from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import BigInteger, DefaultClause, create_engine, func, select, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.base import Base
from planner_core.database.models import CoachConversation, CoachMessage, UserAccount
from server.agent.enums import AgentIntent, AgentRiskLevel
from server.common.exceptions import ConflictError, NotFoundError
from server.observability.tracing import InMemoryTraceSink, SafeTracer
from server.schemas.coach_agent import CoachQueryResponse
from server.schemas.coach_conversation import (
    CoachConversationCreate,
    CoachConversationMessageCreate,
)
from server.services.coach_conversation_service import CoachConversationService
from server.services.conversation_context_builder import ConversationContextBuilder
from server.services.coach_turn_progress import CoachTurnStage


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
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
    db = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()
    db.add_all(
        [
            UserAccount(id=1, username="fictional-chat-user", password_hash="x", status="active"),
            UserAccount(id=2, username="fictional-other-user", password_hash="x", status="active"),
        ]
    )
    db.commit()
    return db


class FakeCoach:
    responses: list[str] = ["completed"]
    seen_contexts: list[list[tuple[str, str]]] = []

    def __init__(self, _db, *, tracer) -> None:
        self.tracer = tracer

    def query(self, *, user_id: int, payload):
        assert user_id == 1
        self.__class__.seen_contexts.append([(item.role, item.content) for item in payload.conversation_context])
        state = self.__class__.responses.pop(0) if self.__class__.responses else "completed"
        if state == "unavailable":
            return CoachQueryResponse(
                request_id=uuid4(),
                trace_id=uuid4(),
                status="UNAVAILABLE",
                intent=AgentIntent.GENERAL_TRAINING_QUESTION,
                risk_level=AgentRiskLevel.UNKNOWN,
                provider_status="FAILED",
                generated_at=datetime.now(timezone.utc),
            )
        return CoachQueryResponse(
            request_id=uuid4(),
            trace_id=uuid4(),
            status="SUCCEEDED",
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
            answer="Fictional safe Coach answer.",
            summary="Fictional summary.",
            risk_level=AgentRiskLevel.LOW,
            provider_status="SUCCEEDED",
            generated_at=datetime.now(timezone.utc),
        )


def _service(db: Session, *, sink: InMemoryTraceSink | None = None) -> CoachConversationService:
    FakeCoach.responses = ["completed"]
    FakeCoach.seen_contexts = []
    return CoachConversationService(
        db,
        coach_service_factory=FakeCoach,
        context_builder=ConversationContextBuilder(max_messages=8, token_budget=800),
        tracer=SafeTracer(sink) if sink else None,
    )


def test_persists_turns_replays_idempotently_and_builds_history() -> None:
    db = _session()
    try:
        service = _service(db)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        first = service.send_message(
            user_id=1,
            conversation_id=conversation.id,
            payload=CoachConversationMessageCreate(client_turn_id="turn_one_001", message="昨天间歇练得怎么样？"),
        )
        replay = service.send_message(
            user_id=1,
            conversation_id=conversation.id,
            payload=CoachConversationMessageCreate(client_turn_id="turn_one_001", message="昨天间歇练得怎么样？"),
        )
        second = service.send_message(
            user_id=1,
            conversation_id=conversation.id,
            payload=CoachConversationMessageCreate(client_turn_id="turn_two_002", message="那周四还能练节奏吗？"),
        )

        assert first.status == replay.status == second.status == "completed"
        assert len(FakeCoach.seen_contexts) == 2
        assert FakeCoach.seen_contexts[0] == []
        assert FakeCoach.seen_contexts[1] == [
            ("user", "昨天间歇练得怎么样？"),
            ("assistant", "Fictional safe Coach answer."),
        ]
        messages = service.list_messages(user_id=1, conversation_id=conversation.id, page=1, page_size=50)
        assert [item.role for item in messages.items] == ["user", "assistant", "user", "assistant"]
        assert messages.total == 4
    finally:
        db.close()


def test_user_isolation_delete_and_pending_turn_conflict() -> None:
    db = _session()
    try:
        service = _service(db)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        with pytest.raises(NotFoundError):
            service.get(user_id=2, conversation_id=conversation.id)
        row = db.scalar(select(CoachConversation).where(CoachConversation.public_id == conversation.id))
        assert row is not None
        row.processing_turn_id = "existing_turn"
        row.processing_started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        with pytest.raises(ConflictError):
            service.send_message(
                user_id=1,
                conversation_id=conversation.id,
                payload=CoachConversationMessageCreate(client_turn_id="other_turn_002", message="今天怎么练？"),
            )
        row.processing_started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        db.commit()
        recovered = service.send_message(
            user_id=1,
            conversation_id=conversation.id,
            payload=CoachConversationMessageCreate(client_turn_id="other_turn_002", message="今天怎么练？"),
        )
        assert recovered.status == "completed"
        service.delete(user_id=1, conversation_id=conversation.id)
        assert db.scalar(select(CoachConversation).where(CoachConversation.id == row.id)) is None
        assert db.scalar(select(CoachMessage).where(CoachMessage.conversation_id == row.id)) is None
    finally:
        db.close()


def test_unavailable_turn_is_retained_and_same_client_turn_can_retry() -> None:
    db = _session()
    try:
        service = _service(db)
        FakeCoach.responses = ["unavailable", "completed"]
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        payload = CoachConversationMessageCreate(client_turn_id="retry_turn_01", message="看看我的状态")
        failed = service.send_message(user_id=1, conversation_id=conversation.id, payload=payload)
        completed = service.send_message(user_id=1, conversation_id=conversation.id, payload=payload)
        messages = service.list_messages(user_id=1, conversation_id=conversation.id, page=1, page_size=20)

        assert failed.status == "failed"
        assert completed.status == "completed"
        assert [item.role for item in messages.items] == ["user", "assistant"]
        assert messages.items[-1].content == "Fictional safe Coach answer."
    finally:
        db.close()


def test_conversation_trace_does_not_export_chat_content() -> None:
    db = _session()
    try:
        sink = InMemoryTraceSink()
        service = _service(db, sink=sink)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        secret = "fictional private chat text"
        service.send_message(
            user_id=1,
            conversation_id=conversation.id,
            payload=CoachConversationMessageCreate(client_turn_id="trace_turn_01", message=secret),
        )
        rendered = str([(item.metadata, item.error_code) for item in sink.spans])
        assert secret not in rendered
        assert any(item.operation == "message.submit" for item in sink.spans)
        assert any(item.operation == "context.build" for item in sink.spans)
    finally:
        db.close()


def test_duplicate_pending_turn_is_rejected_without_creating_more_messages() -> None:
    db = _session()
    try:
        service = _service(db)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        payload = CoachConversationMessageCreate(client_turn_id="pending_turn_01", message="今天怎么练？")
        _user, _assistant, replay, _lease_id = service._reserve_turn(
            user_id=1, conversation_id=conversation.id, payload=payload
        )
        assert replay is False
        with pytest.raises(ConflictError):
            service._reserve_turn(user_id=1, conversation_id=conversation.id, payload=payload)
        count = db.scalar(
            select(func.count()).select_from(CoachMessage).where(
                CoachMessage.conversation_id == db.scalar(
                    select(CoachConversation.id).where(CoachConversation.public_id == conversation.id)
                )
            )
        )
        assert count == 2
    finally:
        db.close()


def test_turn_progress_is_read_only_user_scoped_and_uses_real_counts() -> None:
    db = _session()
    try:
        service = _service(db)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        payload = CoachConversationMessageCreate(client_turn_id="progress_turn_01", message="分析最近训练")
        _user, assistant, _replay, lease_id = service._reserve_turn(
            user_id=1, conversation_id=conversation.id, payload=payload
        )
        assert service._update_turn_progress(
            assistant_message_id=assistant.id,
            client_turn_id=payload.client_turn_id,
            lease_id=lease_id,
            stage=CoachTurnStage.FACTS_READY,
            summary=[{"code": "TRAINING_RECORDS", "message": "已读取训练记录", "count": 18}],
        )
        status = service.get_turn_status(
            user_id=1, conversation_id=conversation.id, client_turn_id=payload.client_turn_id
        )
        assert status.message_status == "pending"
        assert status.progress.stage == "FACTS_READY"
        assert status.progress.summary[0].count == 18
        assert status.progress.sequence >= 1
        with pytest.raises(NotFoundError):
            service.get_turn_status(
                user_id=2, conversation_id=conversation.id, client_turn_id=payload.client_turn_id
            )
    finally:
        db.close()


def test_old_lease_cannot_write_progress_after_a_new_turn_starts() -> None:
    db = _session()
    try:
        service = _service(db)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        first_payload = CoachConversationMessageCreate(client_turn_id="progress_old_01", message="first")
        _first_user, first_assistant, _replay, first_lease = service._reserve_turn(
            user_id=1, conversation_id=conversation.id, payload=first_payload
        )
        row = db.scalar(select(CoachConversation).where(CoachConversation.public_id == conversation.id))
        assert row is not None
        row.processing_started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        db.commit()
        next_payload = CoachConversationMessageCreate(client_turn_id="progress_new_02", message="second")
        _next_user, next_assistant, _replay, next_lease = service._reserve_turn(
            user_id=1, conversation_id=conversation.id, payload=next_payload
        )
        assert not service._update_turn_progress(
            assistant_message_id=first_assistant.id,
            client_turn_id=first_payload.client_turn_id,
            lease_id=first_lease,
            stage=CoachTurnStage.GENERATING,
        )
        current = service.get_turn_status(
            user_id=1, conversation_id=conversation.id, client_turn_id=next_payload.client_turn_id
        )
        assert current.message_id == next_assistant.public_id
        assert current.progress.stage == "QUEUED"
        assert next_lease is not None
    finally:
        db.close()


def test_expired_lease_cannot_overwrite_newer_turn_or_clear_its_lock() -> None:
    db = _session()
    try:
        service = _service(db)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        first_payload = CoachConversationMessageCreate(client_turn_id="expired_turn_01", message="第一条问题")
        first_user, first_assistant, _replay, first_lease_id = service._reserve_turn(
            user_id=1, conversation_id=conversation.id, payload=first_payload
        )
        row = db.scalar(select(CoachConversation).where(CoachConversation.public_id == conversation.id))
        assert row is not None
        row.processing_started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        db.commit()

        second_payload = CoachConversationMessageCreate(client_turn_id="newer_turn_002", message="第二条问题")
        _second_user, second_assistant, _replay, second_lease_id = service._reserve_turn(
            user_id=1, conversation_id=conversation.id, payload=second_payload
        )
        assert second_lease_id is not None

        late = service._complete_turn(
            assistant_message_id=first_assistant.id,
            client_turn_id=first_payload.client_turn_id,
            lease_id=first_lease_id,
            response=FakeCoach(db, tracer=None).query(
                user_id=1, payload=SimpleNamespace(conversation_context=[])
            ),
        )
        assert late is False
        db.expire_all()
        refreshed = db.scalar(select(CoachConversation).where(CoachConversation.public_id == conversation.id))
        old_assistant = db.get(CoachMessage, first_assistant.id)
        assert refreshed is not None
        assert refreshed.processing_turn_id == second_payload.client_turn_id
        assert refreshed.processing_lease_id == second_lease_id
        assert old_assistant is not None and old_assistant.status == "failed"

        assert service._complete_turn(
            assistant_message_id=second_assistant.id,
            client_turn_id=second_payload.client_turn_id,
            lease_id=second_lease_id,
            response=FakeCoach(db, tracer=None).query(
                user_id=1, payload=SimpleNamespace(conversation_context=[])
            ),
        )
        db.expire_all()
        assert db.get(CoachMessage, second_assistant.id).status == "completed"
    finally:
        db.close()


def test_provider_exception_preserves_question_marks_reply_failed_and_allows_retry() -> None:
    class RaisingCoach:
        calls = 0

        def __init__(self, _db, *, tracer) -> None:
            self.tracer = tracer

        def query(self, *, user_id: int, payload):
            del user_id, payload
            self.__class__.calls += 1
            if self.__class__.calls == 1:
                raise TimeoutError("synthetic provider timeout")
            return FakeCoach(db, tracer=None).query(
                user_id=1, payload=SimpleNamespace(conversation_context=[])
            )

    db = _session()
    try:
        RaisingCoach.calls = 0
        service = CoachConversationService(
            db,
            coach_service_factory=RaisingCoach,
            context_builder=ConversationContextBuilder(max_messages=8, token_budget=800),
        )
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        payload = CoachConversationMessageCreate(client_turn_id="timeout_turn_01", message="超时后可重试吗？")
        with pytest.raises(TimeoutError):
            service.send_message(user_id=1, conversation_id=conversation.id, payload=payload)
        failed_messages = service.list_messages(user_id=1, conversation_id=conversation.id, page=1, page_size=20)
        assert [(item.role, item.status) for item in failed_messages.items] == [
            ("user", "completed"),
            ("assistant", "failed"),
        ]
        retried = service.send_message(user_id=1, conversation_id=conversation.id, payload=payload)
        assert retried.status == "completed"
    finally:
        db.close()


def test_late_result_after_delete_cannot_recreate_conversation_or_messages() -> None:
    db = _session()
    try:
        service = _service(db)
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        payload = CoachConversationMessageCreate(client_turn_id="delete_turn_01", message="删除中的会话")
        _user, assistant, _replay, lease_id = service._reserve_turn(
            user_id=1, conversation_id=conversation.id, payload=payload
        )
        assistant_id = assistant.id
        service.delete(user_id=1, conversation_id=conversation.id)
        assert service._complete_turn(
            assistant_message_id=assistant_id,
            client_turn_id=payload.client_turn_id,
            lease_id=lease_id,
            response=FakeCoach(db, tracer=None).query(
                user_id=1, payload=SimpleNamespace(conversation_context=[])
            ),
        ) is False
        assert db.scalar(select(CoachConversation).where(CoachConversation.public_id == conversation.id)) is None
        assert db.scalar(select(CoachMessage).where(CoachMessage.id == assistant_id)) is None
    finally:
        db.close()


def test_ten_turn_history_is_bounded_and_remains_in_stable_sequence_order() -> None:
    db = _session()
    try:
        service = CoachConversationService(
            db,
            coach_service_factory=FakeCoach,
            context_builder=ConversationContextBuilder(max_messages=4, token_budget=800),
        )
        FakeCoach.responses = ["completed"] * 10
        FakeCoach.seen_contexts = []
        conversation = service.create(user_id=1, payload=CoachConversationCreate())
        for index in range(10):
            result = service.send_message(
                user_id=1,
                conversation_id=conversation.id,
                payload=CoachConversationMessageCreate(
                    client_turn_id=f"ten_turn_{index:04d}", message=f"合成连续问题 {index}"
                ),
            )
            assert result.status == "completed"
        messages = service.list_messages(user_id=1, conversation_id=conversation.id, page=1, page_size=50)
        assert [item.sequence_no for item in messages.items] == list(range(1, 21))
        assert len(FakeCoach.seen_contexts) == 10
        assert all(len(context) <= 4 for context in FakeCoach.seen_contexts)
        assert FakeCoach.seen_contexts[-1][0][1] == "合成连续问题 7"
    finally:
        db.close()
