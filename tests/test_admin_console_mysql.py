"""Explicit local MySQL only; synthetic accounts and configuration."""
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4
import re
import pytest
from sqlalchemy import create_engine, delete, inspect, select, text
from sqlalchemy.schema import CreateTable
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from planner_core.database.models import AdminAISettings, AdminAuditEvent, AdminConfigRevision, Base, UserAccount
from scripts.upgrade_admin_console import upgrade
from server.common.exceptions import BadRequestError, ConflictError
from server.schemas.admin_console import AccountAccessUpdate, DraftRequest
from server.services import admin_console_service as service
from server.services.admin_ai_settings_service import get_effective_ai_settings


@pytest.fixture
def engine():
    raw=os.environ.get('GAITLOGIC_ADMIN_TEST_DATABASE_URL')
    if not raw: pytest.skip('Explicit isolated MySQL URL required')
    url=make_url(raw)
    if url.host not in {'127.0.0.1','localhost'} or not (url.database or '').startswith('gaitlogic_test_admin_') or url.get_backend_name()!='mysql':
        pytest.fail('Refusing non-local or non-admin-test database')
    engine=create_engine(url)
    Base.metadata.create_all(engine)
    upgrade(engine);upgrade(engine)
    yield engine
    engine.dispose()


def test_mysql_drafts_publish_rollback_audit_and_cas(engine):
    ids=[]
    with Session(engine) as db:
        admin=UserAccount(username='synthetic-admin-'+uuid4().hex[:12],password_hash='not-a-login',role='admin',status='active')
        runner=UserAccount(username='synthetic-runner-'+uuid4().hex[:12],password_hash='not-a-login',role='user',status='active')
        db.add_all([admin,runner]);db.commit();ids=[admin.id,runner.id]
    try:
        with Session(engine) as db:
            row=db.get(AdminAISettings,1);row.deepseek_api_key='synthetic-private-key';db.commit()
            initial=service.ai_state(db); original=initial['config']
            changed={**original,'model_name':'synthetic-model-v2'}
            draft=service.create_draft(db,DraftRequest(config=changed,expected_fingerprint=initial['fingerprint']),ids[0])
            assert service.ai_state(db)['config']==original
            draft_id=draft.id
        def publish():
            with Session(engine) as db:
                try: service.publish(db,draft_id,initial['fingerprint'],ids[0]);return 'published'
                except ConflictError: return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(lambda _:publish(),range(2)))==['conflict','published']
        with Session(engine) as db:
            assert get_effective_ai_settings(db).ai_model=='synthetic-model-v2'
            state=service.ai_state(db)
            assert 'synthetic-private-key' not in str(state)
            snapshot=db.scalar(select(AdminConfigRevision).where(AdminConfigRevision.status=='SNAPSHOT').order_by(AdminConfigRevision.id.desc()))
            rollback=service.rollback_draft(db,snapshot.id,ids[0])
            assert service.ai_state(db)['config']['model_name']=='synthetic-model-v2'
            service.publish(db,rollback.id,state['fingerprint'],ids[0])
            assert service.ai_state(db)['config']==original
            assert db.get(AdminAISettings,1).deepseek_api_key=='synthetic-private-key'
            with pytest.raises(BadRequestError): service.update_access(db,ids[0],AccountAccessUpdate(role='user',status='active',expected_role='admin',expected_status='active'),ids[0])
            db.rollback()
            service.update_access(db,ids[1],AccountAccessUpdate(role='user',status='disabled',expected_role='user',expected_status='active'),ids[0])
            assert db.get(UserAccount,ids[1]).status=='disabled'
            with pytest.raises(ConflictError): service.update_access(db,ids[1],AccountAccessUpdate(role='user',status='active',expected_role='user',expected_status='active'),ids[0])
            db.rollback()
            page=service.users(db,'synthetic-',1,1)
            assert len(page['items'])==1 and page['total']>=2
            events=list(db.scalars(select(AdminAuditEvent).where(AdminAuditEvent.actor_user_id==ids[0])))
            assert any(item.action=='USER_ACCESS_UPDATED' for item in events)
            assert all('synthetic-private-key' not in str(item.changed_fields) for item in events)
            assert {'admin_config_revisions','admin_audit_events'} <= set(inspect(engine).get_table_names())
    finally:
        with Session(engine) as db:
            db.execute(delete(AdminAuditEvent).where(AdminAuditEvent.actor_user_id.in_(ids)))
            db.execute(delete(AdminConfigRevision).where(AdminConfigRevision.actor_user_id.in_(ids)))
            row=db.get(AdminAISettings,1);row.deepseek_api_key=None;row.updated_by_id=None
            db.flush(); db.execute(delete(UserAccount).where(UserAccount.id.in_(ids)));db.commit()


@pytest.mark.parametrize('interrupted',[False,True])
def test_old_schema_upgrade_preserves_config_and_retries(engine, interrupted):
    # New, explicitly named local test schemas only. Never drop existing tables.
    name='gaitlogic_test_admin_upgrade_'+uuid4().hex[:12]
    with engine.begin() as connection:
        connection.execute(text(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4'))
    legacy=create_engine(engine.url.set(database=name))
    try:
        UserAccount.__table__.create(legacy)
        ddl=str(CreateTable(AdminAISettings.__table__).compile(dialect=legacy.dialect))
        ddl=re.sub(r'\s*config_version INTEGER[^,]*,','',ddl)
        with legacy.begin() as connection:
            connection.execute(text(ddl))
            connection.execute(text("INSERT INTO admin_ai_settings (id,deepseek_model) VALUES (1,'synthetic-preserved-model')"))
            if interrupted:
                connection.execute(text('ALTER TABLE admin_ai_settings ADD COLUMN config_version INT NOT NULL DEFAULT 0'))
        upgrade(legacy);upgrade(legacy)
        with Session(legacy) as db:
            row=db.get(AdminAISettings,1)
            assert row.deepseek_model=='synthetic-preserved-model' and row.config_version==0
        assert {'admin_config_revisions','admin_audit_events'} <= set(inspect(legacy).get_table_names())
    finally: legacy.dispose()


def test_real_http_admin_login_and_console_write(engine):
    from fastapi.testclient import TestClient
    from server.main import create_app
    from server.api.deps import get_db
    from server.services.auth_service import hash_password
    ids=[];password='Synthetic-admin-acceptance-123!'
    with Session(engine) as db:
        for role in ('admin','user'):
            row=UserAccount(username='synthetic-http-'+uuid4().hex[:12],password_hash=hash_password(password),role=role,status='active')
            db.add(row);db.flush();ids.append(row.id)
        db.commit()
    app=create_app()
    def db_session():
        with Session(engine) as db: yield db
    app.dependency_overrides[get_db]=db_session
    try:
        with TestClient(app) as client, Session(engine) as db:
            headers=[]
            for uid in ids:
                response=client.post('/api/auth/login',json={'username':db.get(UserAccount,uid).username,'password':password})
                assert response.status_code==200
                headers.append({'Authorization':'Bearer '+response.json()['access_token']})
            assert client.get('/api/admin/console/ai').status_code==401
            assert client.get('/api/admin/console/ai',headers=headers[1]).status_code==403
            initial=client.get('/api/admin/console/ai',headers=headers[0]).json()
            response=client.post('/api/admin/console/ai/drafts',headers=headers[0],json={'config':initial['config'],'expected_fingerprint':initial['fingerprint']})
            assert response.status_code==201
            rid=response.json()['id']
            publish=client.post(f'/api/admin/console/ai/revisions/{rid}/publish',headers=headers[0],json={'expected_fingerprint':initial['fingerprint']})
            assert publish.status_code==200 and publish.json()['config_version']>initial['config_version']
            assert client.post(f'/api/admin/console/ai/revisions/{rid}/publish',headers=headers[0],json={'expected_fingerprint':publish.json()['fingerprint']}).status_code==409
            assert client.get('/api/admin/console/audit',headers=headers[0]).status_code==200
    finally:
        with Session(engine) as db:
            db.execute(delete(AdminAuditEvent).where(AdminAuditEvent.actor_user_id.in_(ids)))
            db.execute(delete(AdminConfigRevision).where(AdminConfigRevision.actor_user_id.in_(ids)))
            db.get(AdminAISettings,1).updated_by_id=None
            db.flush();db.execute(delete(UserAccount).where(UserAccount.id.in_(ids)));db.commit()
