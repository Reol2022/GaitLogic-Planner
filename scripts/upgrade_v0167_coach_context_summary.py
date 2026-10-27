"""Add idempotent Conversation Summary fields to existing Coach Chat tables."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.session import engine
from scripts.upgrade_v0165_coach_chat import upgrade as upgrade_coach_chat


SUMMARY_COLUMNS = {
    "context_summary_json": "JSON NULL",
    "context_summary_version": "INT NOT NULL DEFAULT 0",
    "context_summary_through_sequence": "INT NOT NULL DEFAULT 0",
    "context_summary_updated_at": "DATETIME NULL",
    "context_summary_status": "VARCHAR(16) NOT NULL DEFAULT 'IDLE'",
    "context_summary_lease_id": "VARCHAR(36) NULL",
    "context_summary_started_at": "DATETIME NULL",
}


def upgrade(connection: Connection) -> None:
    if connection.dialect.name != "mysql":
        raise RuntimeError("The Coach Context migration requires MySQL.")
    upgrade_coach_chat(connection)
    columns = {item["name"] for item in inspect(connection).get_columns("coach_conversations")}
    for name, definition in SUMMARY_COLUMNS.items():
        if name not in columns:
            connection.execute(
                text(f"ALTER TABLE `coach_conversations` ADD COLUMN `{name}` {definition}")
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade GaitLogic Coach Context v2.1 schema.")
    parser.parse_args()
    with engine.begin() as connection:
        upgrade(connection)
    print("Coach Context v2.1 migration upgrade completed")


if __name__ == "__main__":
    main()
