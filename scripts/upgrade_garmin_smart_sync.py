"""Additive, repeatable MySQL upgrade; no production execution by default."""
import argparse
from sqlalchemy import inspect, text
from planner_core.database.models import GarminSmartSyncState


def upgrade(connection):
    if connection.dialect.name != 'mysql':
        raise RuntimeError('MySQL required')
    tables = set(inspect(connection).get_table_names())
    if not {'external_account_connection', 'external_sync_job'} <= tables:
        raise RuntimeError('Install the existing Garmin schema first')
    GarminSmartSyncState.__table__.create(connection, checkfirst=True)
    columns = {c['name'] for c in inspect(connection).get_columns('external_sync_job')}
    for name, default in [('data_scope', 'all'), ('trigger_source', 'manual')]:
        if name not in columns:
            connection.execute(text(f"ALTER TABLE external_sync_job ADD COLUMN `{name}` VARCHAR(16) NOT NULL DEFAULT '{default}'"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Explicitly apply additive DDL to configured database')
    args = parser.parse_args()
    if not args.apply:
        parser.error('Review target configuration and backup first; --apply is required')
    from planner_core.database.session import engine
    with engine.begin() as connection:
        upgrade(connection)
    print('Garmin Smart Sync schema ready')


if __name__ == '__main__':
    main()
