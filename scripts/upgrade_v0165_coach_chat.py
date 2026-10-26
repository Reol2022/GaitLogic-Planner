"""Create the persistent Coach Chat v1 tables on an existing MySQL database.

Fresh installations receive the same structure from ``sql/schema.sql`` and the
SQLAlchemy models. Existing production databases must run this script once after
a backup and before deploying the Coach Chat API.
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

from planner_core.database.models import CoachConversation, CoachMessage
from planner_core.database.session import engine


TABLES = (CoachConversation.__table__, CoachMessage.__table__)


def upgrade(connection: Connection) -> None:
    if connection.dialect.name != "mysql":
        raise RuntimeError("The Coach Chat migration requires MySQL.")
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    for table in TABLES:
        if table.name not in existing:
            table.create(connection, checkfirst=True)
    # Allows a safe rerun if an earlier v1 preview created the tables before
    # stale-turn recovery was added.
    columns = {item["name"] for item in inspect(connection).get_columns("coach_conversations")}
    if "processing_lease_id" not in columns:
        connection.execute(
            text("ALTER TABLE `coach_conversations` ADD COLUMN processing_lease_id VARCHAR(36) NULL")
        )
    if "processing_started_at" not in columns:
        connection.execute(
            text("ALTER TABLE `coach_conversations` ADD COLUMN processing_started_at DATETIME NULL")
        )
    message_columns = {item["name"] for item in inspect(connection).get_columns("coach_messages")}
    additions = {
        "progress_stage": "VARCHAR(32) NOT NULL DEFAULT 'QUEUED'",
        "progress_sequence": "INT NOT NULL DEFAULT 0",
        "progress_summary_json": "JSON NULL",
        "progress_updated_at": "DATETIME NULL",
    }
    for name, definition in additions.items():
        if name not in message_columns:
            connection.execute(text(f"ALTER TABLE `coach_messages` ADD COLUMN `{name}` {definition}"))


def downgrade(connection: Connection, *, allow_destructive: bool) -> None:
    if not allow_destructive:
        raise RuntimeError(
            "Refusing destructive Coach Chat downgrade. Restore a database backup, or rerun with --allow-destructive-downgrade after exporting conversation data."
        )
    if connection.dialect.name != "mysql":
        raise RuntimeError("The Coach Chat migration requires MySQL.")
    # Child table must be removed first because it carries the self-reference.
    CoachMessage.__table__.drop(connection, checkfirst=True)
    CoachConversation.__table__.drop(connection, checkfirst=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade GaitLogic Coach Chat v1 schema.")
    parser.add_argument("action", choices=("upgrade", "downgrade"), nargs="?", default="upgrade")
    parser.add_argument("--allow-destructive-downgrade", action="store_true")
    args = parser.parse_args()
    with engine.begin() as connection:
        if args.action == "upgrade":
            upgrade(connection)
        else:
            downgrade(connection, allow_destructive=args.allow_destructive_downgrade)
    print(f"Coach Chat v1 migration {args.action} completed")


if __name__ == "__main__":
    main()
