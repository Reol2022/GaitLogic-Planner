from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError

from planner_core.config import get_settings
from planner_core.database.models import (
    ExternalAccountConnection,
    ExternalSyncJob,
    RunnerStateSnapshotRecord,
    RunnerStateSnapshotTriggerReceipt,
    UserAccount,
)
from planner_core.enums import RunnerStateSnapshotReceiptStatus
from scripts.upgrade_v0103_runner_state_snapshot_receipts import downgrade, upgrade


def test_receipt_orm_has_exact_constraints_indexes_and_foreign_keys() -> None:
    table = RunnerStateSnapshotTriggerReceipt.__table__
    unique_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert unique_names == {"uq_runner_state_receipt_user_trigger_reference"}
    assert {index.name for index in table.indexes} == {
        "ix_runner_state_receipt_user_created",
        "ix_runner_state_receipt_sync_job",
        "ix_runner_state_receipt_status_locked",
        "ix_runner_state_receipt_snapshot",
    }
    foreign_keys = {
        column.name: next(iter(column.foreign_keys)).ondelete
        for column in (table.c.user_id, table.c.snapshot_id, table.c.sync_job_id)
    }
    assert foreign_keys == {
        "user_id": "CASCADE",
        "snapshot_id": "SET NULL",
        "sync_job_id": "SET NULL",
    }
    assert RunnerStateSnapshotRecord.__table__.constraints
    snapshot_unique_names = {
        constraint.name
        for constraint in RunnerStateSnapshotRecord.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert snapshot_unique_names == {"uq_runner_state_snapshot_user_cutoff_hash"}


def test_migration_source_is_mysql_57_compatible_and_has_no_backfill() -> None:
    source = Path("scripts/upgrade_v0103_runner_state_snapshot_receipts.py").read_text(
        encoding="utf-8"
    )
    assert "checkfirst=False" in source
    assert "INSERT" not in source
    assert "UPDATE" not in source
    assert "IF NOT EXISTS" not in source


def test_mysql_receipt_migration_constraints_foreign_keys_and_round_trip() -> None:
    settings = get_settings()
    database = f"gaitlogic_test_snapshot_receipt_{uuid4().hex[:10]}"
    try:
        admin = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
    except pymysql.MySQLError as exc:
        pytest.skip(f"isolated MySQL is unavailable: {exc.__class__.__name__}")
    created = False
    engine = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        created = True
        url = (
            f"mysql+pymysql://{quote_plus(settings.mysql_user)}:{quote_plus(settings.mysql_password)}@"
            f"{settings.mysql_host}:{settings.mysql_port}/{database}?charset=utf8mb4"
        )
        engine = create_engine(url, future=True)
        UserAccount.__table__.create(engine)
        ExternalAccountConnection.__table__.create(engine)
        ExternalSyncJob.__table__.create(engine)
        RunnerStateSnapshotRecord.__table__.create(engine)
        with engine.begin() as connection:
            upgrade(connection)
            inspector = inspect(connection)
            assert inspector.has_table("runner_state_snapshot_trigger_receipt")
            assert {item["name"] for item in inspector.get_unique_constraints(
                "runner_state_snapshot_trigger_receipt"
            )} == {"uq_runner_state_receipt_user_trigger_reference"}
            indexes = {item["name"] for item in inspector.get_indexes(
                "runner_state_snapshot_trigger_receipt"
            )}
            assert indexes - {"uq_runner_state_receipt_user_trigger_reference"} == {
                "ix_runner_state_receipt_user_created",
                "ix_runner_state_receipt_sync_job",
                "ix_runner_state_receipt_status_locked",
                "ix_runner_state_receipt_snapshot",
            }
            with pytest.raises(OperationalError):
                upgrade(connection)
        with engine.begin() as connection:
            downgrade(connection)
            assert not inspect(connection).has_table("runner_state_snapshot_trigger_receipt")
        with engine.begin() as connection:
            upgrade(connection)
            assert inspect(connection).has_table("runner_state_snapshot_trigger_receipt")
            downgrade(connection)
            assert inspect(connection).has_table("runner_state_snapshots")
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        admin.close()
