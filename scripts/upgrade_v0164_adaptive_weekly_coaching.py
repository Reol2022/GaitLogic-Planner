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


UPGRADE = (
    "ALTER TABLE weekly_review_report ADD COLUMN weekly_facts_fingerprint VARCHAR(64) NULL",
    "ALTER TABLE weekly_review_report ADD COLUMN analysis_snapshot_json JSON NULL",
    "ALTER TABLE weekly_review_report ADD COLUMN readiness_snapshot_json JSON NULL",
    "ALTER TABLE weekly_review_report ADD COLUMN evidence_snapshot_json JSON NULL",
    "ALTER TABLE weekly_review_report ADD COLUMN knowledge_references_json JSON NULL",
    "CREATE INDEX ix_weekly_review_weekly_facts_fingerprint ON weekly_review_report (weekly_facts_fingerprint)",
    "ALTER TABLE training_adjustment_drafts ADD COLUMN review_report_id BIGINT NULL",
    "ALTER TABLE training_adjustment_drafts ADD COLUMN revision INT NOT NULL DEFAULT 1",
    "ALTER TABLE training_adjustment_drafts ADD COLUMN parent_proposal_id BIGINT NULL",
    "ALTER TABLE training_adjustment_drafts ADD COLUMN feedback_json JSON NULL",
    "CREATE INDEX ix_training_adjustment_review_report_id ON training_adjustment_drafts (review_report_id)",
    "CREATE INDEX ix_training_adjustment_parent_proposal_id ON training_adjustment_drafts (parent_proposal_id)",
    "ALTER TABLE training_adjustment_drafts ADD CONSTRAINT uq_training_adjustment_review_revision UNIQUE (review_report_id, revision)",
    "ALTER TABLE training_adjustment_drafts ADD CONSTRAINT fk_training_adjustment_review_report_id FOREIGN KEY (review_report_id) REFERENCES weekly_review_report (id) ON DELETE SET NULL",
    "ALTER TABLE training_adjustment_drafts ADD CONSTRAINT fk_training_adjustment_parent_proposal_id FOREIGN KEY (parent_proposal_id) REFERENCES training_adjustment_drafts (id) ON DELETE SET NULL",
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


def upgrade(connection: Connection) -> None:
    for statement in UPGRADE:
        connection.execute(text(statement))


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
