"""Additive MySQL DDL. Default check only; never infer a production target."""
import argparse
from datetime import datetime, timedelta
from sqlalchemy import delete, inspect, select
from planner_core.database.models import SecurityRateBucket, SecurityRequestLease

TABLES = (SecurityRateBucket.__table__, SecurityRequestLease.__table__)


def upgrade(connection):
    if connection.dialect.name != 'mysql':
        raise RuntimeError('MySQL required')
    if not inspect(connection).has_table('user_account'):
        raise RuntimeError('Install base schema first')
    for table in TABLES:
        table.create(connection, checkfirst=True)
        columns = {item['name'] for item in inspect(connection).get_columns(table.name)}
        indexes = {item['name'] for item in inspect(connection).get_indexes(table.name)}
        if not set(table.columns.keys()) <= columns or not {item.name for item in table.indexes} <= indexes:
            raise RuntimeError('Unexpected security schema; stop for manual review')


def prune(connection, *, now=None):
    now = now or datetime.utcnow()
    # Bounded cleanup only; never delete live gate rows or current buckets.
    connection.execute(delete(SecurityRequestLease).where(SecurityRequestLease.token.in_(
        select(SecurityRequestLease.token).where(SecurityRequestLease.expires_at < now-timedelta(days=1)).limit(1000).subquery().select())))
    live = select(SecurityRequestLease.token).where(SecurityRequestLease.gate_hash == SecurityRateBucket.key_hash,
        SecurityRequestLease.expires_at > now).exists()
    keys = select(SecurityRateBucket.key_hash).where(SecurityRateBucket.expires_at < now-timedelta(days=1), ~live).limit(1000).subquery()
    connection.execute(delete(SecurityRateBucket).where(SecurityRateBucket.key_hash.in_(select(keys.c.key_hash)),
        SecurityRateBucket.expires_at < now-timedelta(days=1)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True, help='Exact configured database name; no password')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--prune', action='store_true', help='Bounded deletion of expired security state only')
    args = parser.parse_args()
    from planner_core.config import get_settings
    if args.database != get_settings().mysql_database:
        parser.error('Target does not match configured database')
    from planner_core.database.session import engine
    with engine.begin() as connection:
        if args.apply:
            upgrade(connection)
        if args.prune:
            prune(connection)
        print({table.name: inspect(connection).has_table(table.name) for table in TABLES})


if __name__ == '__main__':
    main()
