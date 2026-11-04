"""Upgrade only a local, explicitly named gaitlogic_test_* MySQL database.

Existing authorization codes and tokens remain unbound and must be reauthorized.
MySQL DDL commits independently; rerun after correcting an interrupted upgrade.
"""
from __future__ import annotations

import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from planner_core.database.models import McpOAuthGrant


def main() -> None:
    raw = os.environ.get("GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL")
    if not raw:
        raise SystemExit("Explicit isolated test database URL is required")
    url = make_url(raw)
    if url.get_backend_name() != "mysql" or url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").startswith("gaitlogic_test_"):
        raise SystemExit("Refusing non-local or non-test MySQL database")
    engine = create_engine(url)
    try:
        McpOAuthGrant.__table__.create(engine, checkfirst=True)
        for table in ("mcp_oauth_authorization_codes", "mcp_oauth_refresh_tokens"):
            columns = {item["name"] for item in inspect(engine).get_columns(table)}
            with engine.begin() as connection:
                for name, definition in (("resource_uri", "VARCHAR(2048) NULL"), ("grant_id", "VARCHAR(64) NULL")):
                    if name not in columns:
                        connection.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {definition}"))
        print("Isolated OAuth security schema ready")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
