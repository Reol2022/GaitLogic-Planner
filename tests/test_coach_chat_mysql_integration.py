"""Opt-in MySQL acceptance for the Coach Chat migration.

This test is deliberately skipped unless a caller supplies a dedicated local
database URL. It refuses remote hosts and non-test database names so a normal
test command can never touch a development or production database by mistake.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, insert, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from planner_core.database.models import CoachConversation, CoachMessage, UserAccount
from scripts.upgrade_v0165_coach_chat import upgrade


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


@pytest.mark.mysql_integration
def test_coach_chat_migration_is_idempotent_and_enforces_integrity() -> None:
    url = _validated_url()
    engine = create_engine(url, future=True)
    try:
        with engine.begin() as connection:
            # The dedicated database is intentionally reset only for these
            # three tables. Existing GaitLogic databases are never accepted by
            # the URL validation above.
            CoachMessage.__table__.drop(connection, checkfirst=True)
            CoachConversation.__table__.drop(connection, checkfirst=True)
            UserAccount.__table__.drop(connection, checkfirst=True)
            UserAccount.__table__.create(connection, checkfirst=True)

            upgrade(connection)
            upgrade(connection)  # Safe repeated deployment invocation.

            inspector = inspect(connection)
            columns = {item["name"] for item in inspector.get_columns("coach_conversations")}
            assert {"processing_turn_id", "processing_lease_id", "processing_started_at"} <= columns
            indexes = {item["name"] for item in inspector.get_indexes("coach_messages")}
            assert "ix_coach_messages_conversation_sequence" in indexes
            foreign_keys = inspector.get_foreign_keys("coach_messages")
            assert any(item["referred_table"] == "coach_conversations" for item in foreign_keys)

            user_id = connection.execute(
                insert(UserAccount).values(
                    username=f"coach-chat-mysql-{uuid4().hex[:12]}",
                    password_hash="x",
                    status="active",
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
        with engine.begin() as connection:
            conversation_id = connection.scalar(select(CoachConversation.id).limit(1))
            assert conversation_id is not None
            connection.execute(delete(CoachConversation).where(CoachConversation.id == conversation_id))
            assert connection.scalar(select(func.count()).select_from(CoachMessage)) == 0
    finally:
        with engine.begin() as connection:
            CoachMessage.__table__.drop(connection, checkfirst=True)
            CoachConversation.__table__.drop(connection, checkfirst=True)
            UserAccount.__table__.drop(connection, checkfirst=True)
        engine.dispose()
