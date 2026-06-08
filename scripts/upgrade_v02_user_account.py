from __future__ import annotations

from pathlib import Path
import sys
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.config import get_settings
from planner_core.database.session import engine
from server.services.auth_service import hash_password


TABLES_WITH_USER_ID = [
    "training_cycles",
    "training_blocks",
    "planned_workouts",
    "workout_logs",
    "block_reviews",
    "pace_rules",
    "excel_import_jobs",
]


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
            {
                "database_name": database_name,
                "table_name": table_name,
                "column_name": column_name,
            },
        )
    )


def index_exists(connection, table_name: str, index_name: str, database_name: str) -> bool:
    return bool(
        connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.statistics
                WHERE table_schema = :database_name
                  AND table_name = :table_name
                  AND index_name = :index_name
                """
            ),
            {
                "database_name": database_name,
                "table_name": table_name,
                "index_name": index_name,
            },
        )
    )


def ensure_user_table(connection) -> int:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_account (
              id BIGINT NOT NULL AUTO_INCREMENT,
              username VARCHAR(64) NOT NULL,
              email VARCHAR(255) NULL,
              password_hash VARCHAR(255) NOT NULL,
              nickname VARCHAR(64) NULL,
              avatar_url VARCHAR(512) NULL,
              role VARCHAR(32) NOT NULL DEFAULT 'user',
              status VARCHAR(32) NOT NULL DEFAULT 'active',
              last_login_at DATETIME NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              UNIQUE KEY uq_user_account_username (username),
              UNIQUE KEY uq_user_account_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
    )
    demo_id = connection.scalar(text("SELECT id FROM user_account WHERE username = 'demo'"))
    if demo_id:
        return int(demo_id)

    connection.execute(
        text(
            """
            INSERT INTO user_account
            (username, email, password_hash, nickname, avatar_url, role, status, last_login_at)
            VALUES
            (:username, :email, :password_hash, :nickname, NULL, 'user', 'active', NULL)
            """
        ),
        {
            "username": "demo",
            "email": "demo@example.com",
            "password_hash": hash_password("demo123456"),
            "nickname": "Demo Runner",
        },
    )
    return int(connection.scalar(text("SELECT id FROM user_account WHERE username = 'demo'")))


def upgrade_table_user_id(connection, table_name: str, database_name: str, demo_user_id: int) -> None:
    if not table_exists(connection, table_name, database_name):
        print(f"skip missing table: {table_name}")
        return

    if not column_exists(connection, table_name, "user_id", database_name):
        connection.execute(text(f"ALTER TABLE `{table_name}` ADD COLUMN user_id BIGINT NULL"))
        print(f"added column: {table_name}.user_id")

    connection.execute(
        text(f"UPDATE `{table_name}` SET user_id = :user_id WHERE user_id IS NULL"),
        {"user_id": demo_user_id},
    )
    connection.execute(text(f"ALTER TABLE `{table_name}` MODIFY COLUMN user_id BIGINT NOT NULL"))

    index_name = f"ix_{table_name}_user_id"
    if not index_exists(connection, table_name, index_name, database_name):
        connection.execute(text(f"CREATE INDEX `{index_name}` ON `{table_name}` (`user_id`)"))
        print(f"added index: {index_name}")


def main() -> None:
    settings = get_settings()
    with engine.begin() as connection:
        demo_user_id = ensure_user_table(connection)
        for table_name in TABLES_WITH_USER_ID:
            upgrade_table_user_id(connection, table_name, settings.mysql_database, demo_user_id)

    print("v0.2 user_account upgrade complete.")
    print("demo login: demo / demo123456")


if __name__ == "__main__":
    main()
