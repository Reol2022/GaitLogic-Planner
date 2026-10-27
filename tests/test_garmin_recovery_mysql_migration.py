"""Opt-in migration acceptance against a dedicated local gaitlogic_test_* MySQL DB."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from scripts.upgrade_v0166_garmin_recovery import CONNECTION_COLUMNS, RECOVERY_COLUMNS, upgrade


TEST_DATABASE_URL = os.getenv("GAITLOGIC_GARMIN_RECOVERY_TEST_DATABASE_URL")


def _validated_url():
    if not TEST_DATABASE_URL:
        pytest.skip("GAITLOGIC_GARMIN_RECOVERY_TEST_DATABASE_URL is not configured")
    url = make_url(TEST_DATABASE_URL)
    if not url.drivername.startswith("mysql"):
        pytest.fail("Garmin recovery migration acceptance requires MySQL")
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Garmin recovery migration acceptance refuses non-local databases")
    if not (url.database or "").startswith("gaitlogic_test_"):
        pytest.fail("Garmin recovery migration acceptance requires gaitlogic_test_*")
    return url


@pytest.mark.mysql_integration
def test_recovery_migration_is_additive_and_idempotent() -> None:
    engine = create_engine(_validated_url(), future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS `daily_recovery_checkin`"))
            connection.execute(text("DROP TABLE IF EXISTS `external_account_connection`"))
            connection.execute(text(
                "CREATE TABLE `external_account_connection` ("
                "`id` BIGINT NOT NULL AUTO_INCREMENT, `last_successful_sync_at` DATETIME NULL, "
                "PRIMARY KEY (`id`)) ENGINE=InnoDB"
            ))
            connection.execute(text(
                "CREATE TABLE `daily_recovery_checkin` ("
                "`id` BIGINT NOT NULL AUTO_INCREMENT, `hrv_source` VARCHAR(64) NULL, "
                "PRIMARY KEY (`id`)) ENGINE=InnoDB"
            ))
            upgrade(connection)
            upgrade(connection)
            inspector = inspect(connection)
            connection_names = {item["name"] for item in inspector.get_columns("external_account_connection")}
            recovery_names = {item["name"] for item in inspector.get_columns("daily_recovery_checkin")}
            assert set(CONNECTION_COLUMNS) <= connection_names
            assert set(RECOVERY_COLUMNS) <= recovery_names
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS `daily_recovery_checkin`"))
            connection.execute(text("DROP TABLE IF EXISTS `external_account_connection`"))
        engine.dispose()
