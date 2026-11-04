"""Upgrade historical OAuth DDL in a dedicated, initially empty local MySQL schema."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from planner_core.database.models import UserAccount


def test_upgrade_historical_oauth_schema_twice_preserves_records():
    raw = os.getenv("GAITLOGIC_MCP_MIGRATION_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("isolated migration MySQL database is not configured")
    url = make_url(raw)
    if url.get_backend_name() != "mysql" or url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").startswith("gaitlogic_test_mcp_migration_"):
        pytest.fail("Refusing non-local or non-migration MySQL database")
    engine = create_engine(url)
    user_id = None
    try:
        if inspect(engine).get_table_names():
            pytest.fail("Migration database must be initially empty; refusing to alter existing tables")
        original = subprocess.check_output(["git", "show", "86831ad:sql/schema.sql"], text=True, encoding="utf-8")
        UserAccount.__table__.create(engine)
        with engine.begin() as connection:
            for table in ("mcp_oauth_clients", "mcp_oauth_authorization_codes", "mcp_oauth_refresh_tokens"):
                match = re.search(rf"CREATE TABLE IF NOT EXISTS `{table}`\s*\(.*?\) ENGINE=InnoDB[^;]*;", original, re.S)
                assert match is not None
                connection.execute(text(match.group(0)))
            name = "synthetic-migration-" + uuid.uuid4().hex[:12]
            connection.execute(text("INSERT INTO user_account (username,password_hash,status) VALUES (:name,'synthetic','active')"), {"name": name})
            user_id = connection.execute(text("SELECT id FROM user_account WHERE username=:name"), {"name": name}).scalar_one()
            connection.execute(text("INSERT INTO mcp_oauth_authorization_codes (code_hash,client_id,user_id,redirect_uri,code_challenge,scopes_json,expires_at) VALUES (:hash,'synthetic',:uid,'http://localhost/callback','challenge',JSON_ARRAY('mcp:read'),'2099-01-01')"), {"hash": "a" * 64, "uid": user_id})
        # Simulate a previously interrupted MySQL DDL upgrade: one column was
        # committed, while the grant table and remaining columns are absent.
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE mcp_oauth_authorization_codes ADD COLUMN resource_uri VARCHAR(2048) NULL"))
        assert "mcp_oauth_grants" not in inspect(engine).get_table_names()
        env = os.environ.copy()
        env["GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL"] = raw
        for _ in range(2):
            result = subprocess.run([sys.executable, "-B", "-m", "scripts.upgrade_mcp_oauth_security"], env=env, capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, "migration failed in isolated MySQL"
        inspector = inspect(engine)
        assert "mcp_oauth_grants" in inspector.get_table_names()
        assert any(index.get("unique") and index.get("column_names") == ["grant_id"] for index in inspector.get_indexes("mcp_oauth_grants"))
        for table in ("mcp_oauth_authorization_codes", "mcp_oauth_refresh_tokens"):
            assert {"grant_id", "resource_uri"}.issubset({column["name"] for column in inspector.get_columns(table)})
        with engine.connect() as connection:
            row = connection.execute(text("SELECT resource_uri, grant_id FROM mcp_oauth_authorization_codes WHERE code_hash=:hash"), {"hash": "a" * 64}).one()
            assert row.resource_uri is None and row.grant_id is None
    finally:
        if user_id is not None:
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM mcp_oauth_authorization_codes WHERE code_hash=:hash AND user_id=:uid"), {"hash": "a" * 64, "uid": user_id})
                connection.execute(text("DELETE FROM user_account WHERE id=:uid"), {"uid": user_id})
        engine.dispose()
