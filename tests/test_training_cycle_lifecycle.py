from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import BigInteger, DefaultClause, create_engine, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.base import Base
from planner_core.database.models import TrainingCycle, UserAccount
from planner_core.enums import TrainingCycleStatus
from server.schemas.training_cycle import TrainingCycleLifecycleState
from server.services.training_cycle_lifecycle_service import get_lifecycle_snapshot


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
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
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    db = factory()
    db.add(UserAccount(id=1, username="fictional-lifecycle", password_hash="x", status="active"))
    db.commit()
    return db


def test_expired_active_cycle_is_completed_even_with_no_completion_rate() -> None:
    db = _session()
    try:
        end_date = date(2026, 8, 31)
        cycle = TrainingCycle(
            user_id=1,
            name="Fictional summer cycle",
            start_date=date(2026, 8, 1),
            end_date=end_date,
            status=TrainingCycleStatus.active,
            active_user_id=1,
        )
        db.add(cycle)
        db.commit()

        lifecycle = get_lifecycle_snapshot(db, 1, as_of_date=end_date + timedelta(days=1))

        assert lifecycle.state == TrainingCycleLifecycleState.COMPLETED
        assert lifecycle.latest_completed_cycle is not None
        assert lifecycle.latest_completed_cycle.id == cycle.id
        assert lifecycle.latest_completed_cycle.actual_end_date == end_date
        assert lifecycle.transition == "awaiting_next_cycle"
        db.refresh(cycle)
        assert cycle.status == TrainingCycleStatus.completed
        assert cycle.active_user_id is None
    finally:
        db.close()


def test_completed_cycle_and_next_draft_are_distinguished() -> None:
    db = _session()
    try:
        db.add_all(
            [
                TrainingCycle(
                    user_id=1,
                    name="Completed fictional cycle",
                    start_date=date(2026, 7, 1),
                    end_date=date(2026, 7, 31),
                    actual_end_date=date(2026, 7, 31),
                    completed_at=None,
                    status=TrainingCycleStatus.completed,
                ),
                TrainingCycle(
                    user_id=1,
                    name="Next fictional cycle",
                    start_date=date(2026, 9, 15),
                    end_date=date(2026, 10, 15),
                    status=TrainingCycleStatus.draft,
                ),
            ]
        )
        db.commit()

        lifecycle = get_lifecycle_snapshot(db, 1, as_of_date=date(2026, 9, 1))

        assert lifecycle.state == TrainingCycleLifecycleState.COMPLETED
        assert lifecycle.latest_completed_cycle is not None
        assert lifecycle.next_cycle is not None
        assert lifecycle.next_cycle.name == "Next fictional cycle"
        assert lifecycle.transition is None
    finally:
        db.close()


def test_active_cycle_near_end_is_ending_soon() -> None:
    db = _session()
    try:
        db.add(
            TrainingCycle(
                user_id=1,
                name="Active fictional cycle",
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 8),
                status=TrainingCycleStatus.active,
                active_user_id=1,
            )
        )
        db.commit()

        lifecycle = get_lifecycle_snapshot(db, 1, as_of_date=date(2026, 9, 3))

        assert lifecycle.state == TrainingCycleLifecycleState.ENDING_SOON
        assert lifecycle.days_until_end == 5
    finally:
        db.close()


def test_archived_cycle_is_presented_as_cancelled_when_no_other_cycle_exists() -> None:
    db = _session()
    try:
        db.add(
            TrainingCycle(
                user_id=1,
                name="Cancelled fictional cycle",
                status=TrainingCycleStatus.archived,
            )
        )
        db.commit()

        lifecycle = get_lifecycle_snapshot(db, 1, as_of_date=date(2026, 9, 3))

        assert lifecycle.state == TrainingCycleLifecycleState.CANCELLED
    finally:
        db.close()
