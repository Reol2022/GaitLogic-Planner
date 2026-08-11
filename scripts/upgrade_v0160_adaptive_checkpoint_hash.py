"""Upgrade adaptive checkpoint-write identity keys for MySQL utf8mb4 limits.

This is a forward-only data-preserving migration for databases that already
contain the v0.13 checkpoint table.  Fresh databases receive the same schema
through ``planner_core.database.models`` and ``sql/schema.sql``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.adaptive_plan.checkpoint_identity import compute_task_path_hash
from planner_core.database.session import engine


TABLE_NAME = "adaptive_workflow_checkpoint_writes"
UNIQUE_NAME = "uq_adaptive_checkpoint_write_identity"
LEGACY_UNIQUE_COLUMNS = (
    "thread_id",
    "checkpoint_namespace",
    "checkpoint_id",
    "task_id",
    "task_path",
    "write_index",
)
HASH_UNIQUE_COLUMNS = (
    "thread_id",
    "checkpoint_namespace",
    "checkpoint_id",
    "task_id",
    "task_path_hash",
    "write_index",
)


def _unique_columns(connection: Connection) -> tuple[str, ...] | None:
    for constraint in inspect(connection).get_unique_constraints(TABLE_NAME):
        if constraint.get("name") == UNIQUE_NAME:
            return tuple(constraint.get("column_names") or ())
    return None


def _backfill_hashes(connection: Connection) -> None:
    rows = connection.execute(
        text(
            f"SELECT id, task_path FROM `{TABLE_NAME}` "
            "WHERE task_path_hash IS NULL"
        )
    ).mappings()
    for row in rows:
        connection.execute(
            text(
                f"UPDATE `{TABLE_NAME}` SET task_path_hash = :task_path_hash "
                "WHERE id = :id"
            ),
            {
                "id": row["id"],
                "task_path_hash": compute_task_path_hash(row["task_path"]),
            },
        )


def upgrade(connection: Connection) -> None:
    """Backfill the binary digest and replace only the oversized key member."""

    if connection.dialect.name != "mysql":
        raise RuntimeError("The adaptive checkpoint hash migration requires MySQL.")
    inspector = inspect(connection)
    if TABLE_NAME not in inspector.get_table_names():
        raise RuntimeError(f"Required table {TABLE_NAME!r} does not exist.")

    column_names = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    current_unique = _unique_columns(connection)
    if current_unique == HASH_UNIQUE_COLUMNS and "task_path_hash" in column_names:
        return
    if current_unique != LEGACY_UNIQUE_COLUMNS:
        raise RuntimeError("Checkpoint-write identity constraint does not match the supported legacy schema.")

    connection.execute(
        text(f"ALTER TABLE `{TABLE_NAME}` ADD COLUMN task_path_hash BINARY(32) NULL")
    )
    _backfill_hashes(connection)
    missing_count = connection.scalar(
        text(f"SELECT COUNT(*) FROM `{TABLE_NAME}` WHERE task_path_hash IS NULL")
    )
    if missing_count:
        raise RuntimeError("Checkpoint-write hash backfill left NULL values.")
    connection.execute(text(f"ALTER TABLE `{TABLE_NAME}` DROP INDEX `{UNIQUE_NAME}`"))
    connection.execute(
        text(f"ALTER TABLE `{TABLE_NAME}` MODIFY COLUMN task_path_hash BINARY(32) NOT NULL")
    )
    connection.execute(
        text(
            f"ALTER TABLE `{TABLE_NAME}` ADD UNIQUE KEY `{UNIQUE_NAME}` "
            "(thread_id, checkpoint_namespace, checkpoint_id, task_id, task_path_hash, write_index)"
        )
    )


def downgrade(connection: Connection) -> None:
    """Refuse a destructive downgrade to an index MySQL cannot create."""

    del connection
    raise RuntimeError(
        "No safe downgrade exists: the legacy utf8mb4 composite index exceeds MySQL's key-width limit."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upgrade adaptive checkpoint write identity keys for MySQL."
    )
    parser.add_argument("action", choices=("upgrade", "downgrade"), nargs="?", default="upgrade")
    args = parser.parse_args()
    with engine.begin() as connection:
        (upgrade if args.action == "upgrade" else downgrade)(connection)
    print(f"v0.16 adaptive checkpoint hash migration {args.action} completed")


if __name__ == "__main__":
    main()
