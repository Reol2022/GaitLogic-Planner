"""Add console tables only. Never infer a production target from general settings."""
import argparse
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from planner_core.database.models import AdminAuditEvent, AdminConfigRevision, AdminAISettings
from server.services.admin_console_service import read_config, MAPPING


def upgrade(engine):
    if engine.dialect.name != 'mysql':
        raise RuntimeError('MySQL is required')
    existing=set(inspect(engine).get_table_names())
    if not {'user_account','admin_ai_settings'} <= existing:
        raise RuntimeError('Install the existing application schema first')
    if 'config_version' not in {column['name'] for column in inspect(engine).get_columns('admin_ai_settings')}:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE admin_ai_settings ADD COLUMN config_version INT NOT NULL DEFAULT 0'))
    AdminConfigRevision.__table__.create(engine,checkfirst=True)
    AdminAuditEvent.__table__.create(engine,checkfirst=True)
    with Session(engine) as db:
        if db.scalar(select(AdminAISettings).where(AdminAISettings.id==1)) is None:
            from planner_core.config import get_settings
            values={MAPPING.get(key,key):value for key,value in read_config().model_dump().items()}
            db.add(AdminAISettings(id=1,deepseek_base_url=get_settings().deepseek_base_url,**values))
            db.commit()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',required=True,help='Exact expected schema name; the URL is never printed')
    parser.add_argument('--allow-non-test',action='store_true',help='Explicit reviewed deployment only')
    args=parser.parse_args()
    raw=os.environ.get('GAITLOGIC_ADMIN_MIGRATION_DATABASE_URL')
    if not raw: parser.error('Set GAITLOGIC_ADMIN_MIGRATION_DATABASE_URL securely first')
    from sqlalchemy.engine import make_url
    url=make_url(raw)
    if url.database!=args.database: parser.error('Database name does not match')
    if not args.allow_non_test and (url.host not in {'127.0.0.1','localhost'} or not args.database.startswith('gaitlogic_test_')):
        parser.error('Default mode allows only isolated local gaitlogic_test_* schemas')
    engine=create_engine(url)
    try: upgrade(engine)
    finally: engine.dispose()
    print('Admin console schema upgrade completed')


if __name__=='__main__': main()
