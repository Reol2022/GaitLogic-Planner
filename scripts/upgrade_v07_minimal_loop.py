from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.config import get_settings
from planner_core.database.session import engine


def column_exists(connection, table_name: str, column_name: str, database_name: str) -> bool:
    return bool(
        connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = :database_name
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"database_name": database_name, "table_name": table_name, "column_name": column_name},
        )
    )


def table_exists(connection, table_name: str, database_name: str) -> bool:
    return bool(
        connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = :database_name
                  AND table_name = :table_name
                """
            ),
            {"database_name": database_name, "table_name": table_name},
        )
    )


def main() -> None:
    settings = get_settings()
    with engine.begin() as connection:
        if not column_exists(connection, "user_account", "ui_mode", settings.mysql_database):
            connection.execute(
                text("ALTER TABLE user_account ADD COLUMN ui_mode VARCHAR(16) NOT NULL DEFAULT 'simple' AFTER role")
            )

        if not table_exists(connection, "usage_event", settings.mysql_database):
            connection.execute(
                text(
                    """
                    CREATE TABLE usage_event (
                      id BIGINT NOT NULL AUTO_INCREMENT,
                      user_id BIGINT NULL,
                      event_name VARCHAR(64) NOT NULL,
                      page_path VARCHAR(255) NULL,
                      metadata_json JSON NULL,
                      occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      PRIMARY KEY (id),
                      KEY ix_usage_event_user_id (user_id),
                      KEY ix_usage_event_user_occurred (user_id, occurred_at),
                      KEY ix_usage_event_event_occurred (event_name, occurred_at),
                      CONSTRAINT fk_usage_event_user_id
                        FOREIGN KEY (user_id) REFERENCES user_account (id) ON DELETE SET NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
        if not table_exists(connection, "admin_system_settings", settings.mysql_database):
            connection.execute(
                text(
                    """
                    CREATE TABLE admin_system_settings (
                      id BIGINT NOT NULL AUTO_INCREMENT,
                      auth_entry_mode VARCHAR(32) NOT NULL DEFAULT 'standalone',
                      allow_public_registration TINYINT(1) NOT NULL DEFAULT 1,
                      updated_by_id BIGINT NULL,
                      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                      PRIMARY KEY (id),
                      KEY ix_admin_system_settings_updated_by_id (updated_by_id),
                      CONSTRAINT fk_admin_system_settings_updated_by_id
                        FOREIGN KEY (updated_by_id) REFERENCES user_account (id) ON DELETE SET NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
    print("v0.7 minimal loop database upgrade completed.")


if __name__ == "__main__":
    main()
