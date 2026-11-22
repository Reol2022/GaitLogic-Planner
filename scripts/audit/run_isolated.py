"""Provision only an exact local gaitlogic_test_* schema and restricted account.

Coordinator credentials must be explicitly supplied as MYSQL_HOST/PORT/USER/PASSWORD.
No .env inference; no credentials are printed. Not a production migration tool.
"""
import os
import re
import secrets
import sys
from pathlib import Path
from uuid import uuid4

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def main():
    private = Path(__file__).resolve().parents[2] / '.audit-private'
    private.mkdir(exist_ok=True)
    if not (private / '.gitignore').exists():
        (private / '.gitignore').write_text('*\n', encoding='utf-8')
    assert os.environ['MYSQL_HOST'] == '127.0.0.1'
    assert os.environ['MYSQL_PORT'] == '3307'
    assert os.environ.get('MYSQL_USER') and 'MYSQL_PASSWORD' in os.environ
    name = 'gaitlogic_test_mcp_migration_audit_' + uuid4().hex[:10]
    account = 'gl_audit_' + uuid4().hex[:10]
    assert re.fullmatch(r'gaitlogic_test_mcp_migration_audit_[0-9a-f]{10}', name)
    password = secrets.token_urlsafe(32)
    adaptive = '--adaptive-fixtures' in sys.argv
    if adaptive:
        sys.argv.remove('--adaptive-fixtures')
        assert 'tests/test_adaptive_plan_hitl.py' in sys.argv
    garmin_material = '--garmin-material-fixtures' in sys.argv
    if garmin_material:
        sys.argv.remove('--garmin-material-fixtures')
        assert 'tests/test_garmin_sync_material_change.py' in sys.argv
    ai_quota = '--ai-plan-quota-fixtures' in sys.argv
    if ai_quota:
        sys.argv.remove('--ai-plan-quota-fixtures')
        assert 'tests/test_ai_plan_quota.py' in sys.argv
    weekly = '--weekly-stats-fixtures' in sys.argv
    if weekly:
        sys.argv.remove('--weekly-stats-fixtures')
        assert 'tests/test_weekly_review_stats.py' in sys.argv
    coordinator = pymysql.connect(host='127.0.0.1', port=3307, user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], autocommit=True, connect_timeout=5)
    database_created = account_created = False
    try:
        with coordinator.cursor() as cur:
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
            database_created = True
            cur.execute('CREATE USER %s@%s IDENTIFIED BY %s', (account, '127.0.0.1', password))
            account_created = True
            # Escape LIKE wildcard characters in a schema grant.
            grant_name = name.replace('_', '\\_')
            cur.execute(f'GRANT ALL PRIVILEGES ON `{grant_name}`.* TO %s@%s', (account, '127.0.0.1'))
            if adaptive:
                # Legacy fixture creates/drops random schemas in this family;
                # never grant global CREATE/DROP or privileges on business DBs.
                cur.execute('GRANT ALL PRIVILEGES ON `gaitlogic\\_test\\_adaptive\\_%%`.* TO %s@%s', (account, '127.0.0.1'))
            if garmin_material:
                cur.execute('GRANT ALL PRIVILEGES ON `gaitlogic\\_test\\_garmin\\_material\\_%%`.* TO %s@%s', (account, '127.0.0.1'))
                cur.execute('GRANT ALL PRIVILEGES ON `gaitlogic\\_test\\_garmin\\_migration\\_%%`.* TO %s@%s', (account, '127.0.0.1'))
            if ai_quota:
                cur.execute('GRANT ALL PRIVILEGES ON `gaitlogic\\_test\\_ai\\_plan\\_%%`.* TO %s@%s', (account, '127.0.0.1'))
            if weekly:
                cur.execute('GRANT ALL PRIVILEGES ON `gaitlogic\\_test\\_weekly\\_stats\\_%%`.* TO %s@%s', (account, '127.0.0.1'))
        url = URL.create('mysql+pymysql', username=account, password=password, host='127.0.0.1', port=3307, database=name)
        os.environ.update(MYSQL_DATABASE=name, MYSQL_USER=account, MYSQL_PASSWORD=password, GARMIN_SMART_SYNC_ENABLED='false', AGENT_TRACING_ENABLED='false', GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL=url.render_as_string(hide_password=False))
        args = sys.argv[1:]
        if '--empty-schema' in args:
            args.remove('--empty-schema')
            os.environ['GAITLOGIC_MCP_MIGRATION_TEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
        else:
            from planner_core.database.base import Base
            import planner_core.database.models  # noqa: F401
            engine = create_engine(url)
            try:
                Base.metadata.create_all(engine)
            finally:
                engine.dispose()
        import pytest
        return pytest.main(['-p', 'no:cacheprovider', '-q', *args])
    finally:
        with coordinator.cursor() as cur:
            if database_created:
                cur.execute(f'DROP DATABASE `{name}`')
            if account_created:
                cur.execute('DROP USER %s@%s', (account, '127.0.0.1'))
        coordinator.close()


if __name__ == '__main__':
    raise SystemExit(main())
