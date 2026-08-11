from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.adaptive_plan.checkpoint_identity import (
    TASK_PATH_HASH_BYTES,
    compute_task_path_hash,
)
from planner_core.config import get_settings
from planner_core.database.models import AdaptiveWorkflowCheckpointWriteRecord
from scripts.upgrade_v0160_adaptive_checkpoint_hash import (
    HASH_UNIQUE_COLUMNS,
    TABLE_NAME,
    UNIQUE_NAME,
    upgrade,
)


def _record(*, record_id: int, task_path: str) -> AdaptiveWorkflowCheckpointWriteRecord:
    return AdaptiveWorkflowCheckpointWriteRecord(
        id=record_id,
        thread_id="fixture-thread",
        checkpoint_namespace="fixture-namespace",
        checkpoint_id="fixture-checkpoint",
        task_id="fixture-task",
        task_path=task_path,
        write_index=0,
        channel="fixture-channel",
        value_type="json",
        value_blob=b"{}",
    )


def test_task_path_hash_is_deterministic_binary_sha256() -> None:
    path = "workflow/阶段/节点"
    digest = compute_task_path_hash(path)
    assert digest == compute_task_path_hash(path)
    assert len(digest) == TASK_PATH_HASH_BYTES
    assert digest != compute_task_path_hash(path + "/next")
    with pytest.raises(TypeError, match="task_path"):
        compute_task_path_hash(None)


def test_sqlite_write_invariant_preserves_long_unicode_path(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'checkpoint.db'}", future=True)
    AdaptiveWorkflowCheckpointWriteRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    original_path = "路径/" + "阶段/" * 100
    changed_path = original_path + "完成"
    try:
        with factory.begin() as db:
            record = _record(record_id=1, task_path=original_path)
            db.add(record)
        with factory() as db:
            saved = db.scalar(select(AdaptiveWorkflowCheckpointWriteRecord))
            assert saved is not None
            assert saved.task_path == original_path
            assert saved.task_path_hash == compute_task_path_hash(original_path)
            saved.task_path = changed_path
            db.commit()
            assert saved.task_path_hash == compute_task_path_hash(changed_path)
            assert len(saved.task_path_hash) == TASK_PATH_HASH_BYTES
        with factory() as db:
            db.add(_record(record_id=2, task_path=changed_path))
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()
        with factory.begin() as db:
            db.add(_record(record_id=3, task_path=original_path))
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def legacy_mysql_engine():
    settings = get_settings()
    database = f"gaitlogic_test_checkpoint_hash_{uuid4().hex[:10]}"
    try:
        admin = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    except pymysql.MySQLError as exc:
        pytest.skip(f"isolated MySQL is unavailable: {exc.__class__.__name__}")
    finally:
        if "admin" in locals():
            admin.close()
    url = (
        f"mysql+pymysql://{quote_plus(settings.mysql_user)}:{quote_plus(settings.mysql_password)}@"
        f"{settings.mysql_host}:{settings.mysql_port}/{database}?charset=utf8mb4"
    )
    engine = create_engine(url, future=True)
    try:
        # latin1 only simulates the historical legacy index shape.  It makes
        # the old 1024-character composite key creatable on modern MySQL so
        # this migration can be verified without changing server-wide limits.
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE adaptive_workflow_checkpoint_writes ("
                    "id BIGINT NOT NULL AUTO_INCREMENT, "
                    "thread_id VARCHAR(128) NOT NULL, "
                    "checkpoint_namespace VARCHAR(128) NOT NULL DEFAULT '', "
                    "checkpoint_id VARCHAR(128) NOT NULL, "
                    "task_id VARCHAR(128) NOT NULL, "
                    "task_path VARCHAR(512) NOT NULL DEFAULT '', "
                    "write_index INT NOT NULL, "
                    "channel VARCHAR(128) NOT NULL, "
                    "value_type VARCHAR(64) NOT NULL, "
                    "value_blob LONGBLOB NOT NULL, "
                    "PRIMARY KEY (id), "
                    "UNIQUE KEY uq_adaptive_checkpoint_write_identity "
                    "(thread_id, checkpoint_namespace, checkpoint_id, task_id, task_path, write_index)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=latin1"
                )
            )
        yield engine
    finally:
        engine.dispose()
        cleanup = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
        with cleanup.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cleanup.close()


def test_mysql_upgrade_backfills_hash_and_replaces_only_index_member(legacy_mysql_engine) -> None:
    long_path = "legacy/" + "segment/" * 50
    with legacy_mysql_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO adaptive_workflow_checkpoint_writes "
                "(thread_id, checkpoint_namespace, checkpoint_id, task_id, task_path, write_index, channel, value_type, value_blob) "
                "VALUES ('thread', 'namespace', 'checkpoint', 'task', :task_path, 0, 'channel', 'json', :value_blob)"
            ),
            {"task_path": long_path, "value_blob": b"{}"},
        )
        upgrade(connection)
        upgrade(connection)
        stored_path, stored_hash = connection.execute(
            text("SELECT task_path, task_path_hash FROM adaptive_workflow_checkpoint_writes")
        ).one()
        assert stored_path == long_path
        assert bytes(stored_hash) == compute_task_path_hash(long_path)
        unique = next(
            item
            for item in inspect(connection).get_unique_constraints(TABLE_NAME)
            if item.get("name") == UNIQUE_NAME
        )
        assert tuple(unique["column_names"]) == HASH_UNIQUE_COLUMNS
        columns = {item["name"]: item for item in inspect(connection).get_columns(TABLE_NAME)}
        assert columns["task_path_hash"]["nullable"] is False
