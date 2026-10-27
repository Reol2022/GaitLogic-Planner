"""Add Garmin recovery synchronization fields to an existing MySQL schema."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.session import engine


CONNECTION_COLUMNS = {
    "recovery_last_attempt_at": "DATETIME NULL",
    "recovery_last_successful_sync_at": "DATETIME NULL",
    "recovery_last_error_code": "VARCHAR(64) NULL",
}

RECOVERY_COLUMNS = {
    "sleep_source": "VARCHAR(32) NULL",
    "resting_heart_rate_source": "VARCHAR(32) NULL",
    "sleep_score": "INT NULL",
    "average_stress": "INT NULL",
    "max_stress": "INT NULL",
    "body_battery_start": "INT NULL",
    "body_battery_end": "INT NULL",
    "body_battery_high": "INT NULL",
    "body_battery_low": "INT NULL",
    "respiration_rate": "DECIMAL(8, 2) NULL",
    "pulse_ox": "DECIMAL(8, 2) NULL",
    "device_provider": "VARCHAR(32) NULL",
    "device_data_status": "VARCHAR(32) NULL",
    "device_synced_at": "DATETIME NULL",
    "provider_updated_at": "DATETIME NULL",
    "device_missing_fields_json": "JSON NULL",
    "device_limitations_json": "JSON NULL",
}


def _add_missing(connection: Connection, table: str, columns: dict[str, str]) -> None:
    existing = {item["name"] for item in inspect(connection).get_columns(table)}
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {definition}"))


def upgrade(connection: Connection) -> None:
    if connection.dialect.name != "mysql":
        raise RuntimeError("The Garmin recovery migration requires MySQL.")
    tables = set(inspect(connection).get_table_names())
    required = {"external_account_connection", "daily_recovery_checkin"}
    missing = required - tables
    if missing:
        raise RuntimeError(f"Missing prerequisite tables: {', '.join(sorted(missing))}")
    _add_missing(connection, "external_account_connection", CONNECTION_COLUMNS)
    _add_missing(connection, "daily_recovery_checkin", RECOVERY_COLUMNS)


def main() -> None:
    with engine.begin() as connection:
        upgrade(connection)
    print("Garmin recovery v0.16.6 migration completed")


if __name__ == "__main__":
    main()
