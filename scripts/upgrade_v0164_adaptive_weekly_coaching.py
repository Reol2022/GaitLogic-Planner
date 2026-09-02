"""Add immutable review-snapshot and versioned-proposal fields (v0.16.4).

Legacy weekly reviews deliberately keep NULL ``weekly_facts_fingerprint``.  They
remain queryable, but revision is refused because freshness cannot be proven.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import text
from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.session import engine


UPGRADE_COLUMNS = (
    ("weekly_review_report", "weekly_facts_fingerprint", "VARCHAR(64) NULL"),
    ("weekly_review_report", "analysis_snapshot_json", "JSON NULL"),
    ("weekly_review_report", "readiness_snapshot_json", "JSON NULL"),
    ("weekly_review_report", "evidence_snapshot_json", "JSON NULL"),
    ("weekly_review_report", "knowledge_references_json", "JSON NULL"),
    ("training_adjustment_drafts", "review_report_id", "BIGINT NULL"),
    ("training_adjustment_drafts", "revision", "INT NOT NULL DEFAULT 1"),
    ("training_adjustment_drafts", "parent_proposal_id", "BIGINT NULL"),
    ("training_adjustment_drafts", "feedback_json", "JSON NULL"),
)

UPGRADE_INDEXES = (
    ("weekly_review_report", "ix_weekly_review_weekly_facts_fingerprint", "weekly_facts_fingerprint"),
    ("training_adjustment_drafts", "ix_training_adjustment_review_report_id", "review_report_id"),
    ("training_adjustment_drafts", "ix_training_adjustment_parent_proposal_id", "parent_proposal_id"),
)

UPGRADE_CONSTRAINTS = (
    ("training_adjustment_drafts", "uq_training_adjustment_review_revision", "UNIQUE (review_report_id, revision)"),
    ("training_adjustment_drafts", "fk_training_adjustment_review_report_id", "FOREIGN KEY (review_report_id) REFERENCES weekly_review_report (id) ON DELETE SET NULL"),
    ("training_adjustment_drafts", "fk_training_adjustment_parent_proposal_id", "FOREIGN KEY (parent_proposal_id) REFERENCES training_adjustment_drafts (id) ON DELETE SET NULL"),
)

DOWNGRADE = (
    "ALTER TABLE training_adjustment_drafts DROP FOREIGN KEY fk_training_adjustment_parent_proposal_id",
    "ALTER TABLE training_adjustment_drafts DROP FOREIGN KEY fk_training_adjustment_review_report_id",
    "ALTER TABLE training_adjustment_drafts DROP INDEX uq_training_adjustment_review_revision",
    "ALTER TABLE training_adjustment_drafts DROP INDEX ix_training_adjustment_parent_proposal_id",
    "ALTER TABLE training_adjustment_drafts DROP INDEX ix_training_adjustment_review_report_id",
    "ALTER TABLE training_adjustment_drafts DROP COLUMN feedback_json",
    "ALTER TABLE training_adjustment_drafts DROP COLUMN parent_proposal_id",
    "ALTER TABLE training_adjustment_drafts DROP COLUMN revision",
    "ALTER TABLE training_adjustment_drafts DROP COLUMN review_report_id",
    "DROP INDEX ix_weekly_review_weekly_facts_fingerprint ON weekly_review_report",
    "ALTER TABLE weekly_review_report DROP COLUMN knowledge_references_json",
    "ALTER TABLE weekly_review_report DROP COLUMN evidence_snapshot_json",
    "ALTER TABLE weekly_review_report DROP COLUMN readiness_snapshot_json",
    "ALTER TABLE weekly_review_report DROP COLUMN analysis_snapshot_json",
    "ALTER TABLE weekly_review_report DROP COLUMN weekly_facts_fingerprint",
)


def _exists(connection: Connection, *, catalog: str, table: str, name: str) -> bool:
    """Return whether a named schema object exists in the current database."""

    column = "column_name" if catalog == "columns" else "index_name"
    if catalog == "table_constraints":
        column = "constraint_name"
    statement = text(
        f"SELECT COUNT(*) FROM information_schema.{catalog} "
        f"WHERE table_schema = DATABASE() AND table_name = :table_name AND {column} = :name"
    )
    return bool(connection.execute(statement, {"table_name": table, "name": name}).scalar())


def upgrade(connection: Connection) -> None:
    """Apply only missing DDL so a previously interrupted upgrade can resume."""

    for table, column, definition in UPGRADE_COLUMNS:
        if not _exists(connection, catalog="columns", table=table, name=column):
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

    for table, index, columns in UPGRADE_INDEXES:
        if not _exists(connection, catalog="statistics", table=table, name=index):
            connection.execute(text(f"CREATE INDEX {index} ON {table} ({columns})"))

    for table, constraint, definition in UPGRADE_CONSTRAINTS:
        if not _exists(connection, catalog="table_constraints", table=table, name=constraint):
            connection.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} {definition}"))


def downgrade(connection: Connection) -> None:
    for statement in DOWNGRADE:
        connection.execute(text(statement))


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate v0.16.4 adaptive weekly coaching lifecycle.")
    parser.add_argument("action", choices=("upgrade", "downgrade"), nargs="?", default="upgrade")
    action = parser.parse_args().action
    with engine.begin() as connection:
        (upgrade if action == "upgrade" else downgrade)(connection)
    print(f"v0.16.4 adaptive weekly coaching migration {action} completed")


if __name__ == "__main__":
    main()
