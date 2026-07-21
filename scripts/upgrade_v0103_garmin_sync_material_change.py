from __future__ import annotations

import argparse
from pathlib import Path
import sys
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.session import engine


def upgrade(connection: Connection) -> None:
    """Add C2.3-A job identity and committed material-change result fields."""

    _require_mysql(connection)
    connection.execute(
        text(
            """
            ALTER TABLE `external_sync_job`
              ADD COLUMN `sync_run_id` VARCHAR(36) NULL AFTER `idempotency_key`,
              ADD COLUMN `is_committed` TINYINT(1) NOT NULL DEFAULT 0 AFTER `failed_count`,
              ADD COLUMN `committed_at` DATETIME NULL AFTER `is_committed`,
              ADD COLUMN `created_log_count` INT NOT NULL DEFAULT 0 AFTER `committed_at`,
              ADD COLUMN `updated_log_count` INT NOT NULL DEFAULT 0 AFTER `created_log_count`,
              ADD COLUMN `unchanged_activity_count` INT NOT NULL DEFAULT 0 AFTER `updated_log_count`,
              ADD COLUMN `runner_state_affecting_change_count` INT NOT NULL DEFAULT 0
                AFTER `unchanged_activity_count`
            """
        )
    )
    job_ids = list(
        connection.execute(
            text("SELECT `id` FROM `external_sync_job` WHERE `sync_run_id` IS NULL ORDER BY `id`")
        ).scalars()
    )
    if job_ids:
        connection.execute(
            text("UPDATE `external_sync_job` SET `sync_run_id` = :sync_run_id WHERE `id` = :job_id"),
            [{"job_id": int(job_id), "sync_run_id": str(uuid4())} for job_id in job_ids],
        )
    remaining = connection.scalar(
        text("SELECT COUNT(*) FROM `external_sync_job` WHERE `sync_run_id` IS NULL")
    )
    if int(remaining or 0) != 0:
        raise RuntimeError("sync_run_id backfill left NULL rows")
    connection.execute(
        text(
            """
            ALTER TABLE `external_sync_job`
              MODIFY COLUMN `sync_run_id` VARCHAR(36) NOT NULL,
              ADD INDEX `ix_external_sync_job_sync_run_id` (`sync_run_id`)
            """
        )
    )


def downgrade(connection: Connection) -> None:
    _require_mysql(connection)
    connection.execute(
        text(
            """
            ALTER TABLE `external_sync_job`
              DROP INDEX `ix_external_sync_job_sync_run_id`,
              DROP COLUMN `runner_state_affecting_change_count`,
              DROP COLUMN `unchanged_activity_count`,
              DROP COLUMN `updated_log_count`,
              DROP COLUMN `created_log_count`,
              DROP COLUMN `committed_at`,
              DROP COLUMN `is_committed`,
              DROP COLUMN `sync_run_id`
            """
        )
    )


def _require_mysql(connection: Connection) -> None:
    if connection.dialect.name != "mysql":
        raise RuntimeError("Garmin sync material-change migration requires an isolated MySQL database")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Garmin sync material-change contract.")
    parser.add_argument("action", choices=("upgrade", "downgrade"), nargs="?", default="upgrade")
    args = parser.parse_args()
    with engine.begin() as connection:
        if args.action == "upgrade":
            upgrade(connection)
        else:
            downgrade(connection)
    print(f"Garmin sync material-change migration {args.action} completed")


if __name__ == "__main__":
    main()
