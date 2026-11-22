"""Local test MySQL only; no Garmin, paid LLM, production or real user data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import multiprocessing
import os
from threading import Event
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.orm import sessionmaker

from tests.test_mcp_facts_v3_mysql import engine, sample
from planner_core.config import get_settings
from planner_core.database.models import SecurityRateBucket, SecurityRequestLease
from server.common.exceptions import AppError, TooManyRequestsError, ServiceUnavailableError, app_error_handler
from server.security import admission
from server.security.middleware import SecurityMiddleware


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv('SECURITY_CONTROLS_ENABLED', 'true')
    monkeypatch.setenv('GARMIN_SMART_SYNC_ENABLED', 'false')
    monkeypatch.setenv('JWT_SECRET_KEY', 'synthetic-security-mysql-only')
    monkeypatch.setenv('SECURITY_RATE_LIMITS', '{}')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_real_connections_atomically_bound_budget_and_recover_window(engine):
    factory = sessionmaker(engine)
    subject = uuid4().hex
    settings = get_settings().model_copy(update={'security_rate_limits': {'coach_day': 3}})
    now = datetime.utcnow().replace(microsecond=0)
    def attempt(_):
        try:
            admission.consume(factory, [('coach_day', subject)], now=now, settings=settings)
            return True
        except TooManyRequestsError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert sum(outcomes) == 3
    with factory() as db:
        bucket = db.get(SecurityRateBucket, admission.opaque_key('coach_day', subject))
        assert bucket.count == 3
    admission.consume(factory, [('coach_day', subject)], now=now+timedelta(days=1), settings=settings)


def process_consume(subject, queue):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    raw = os.environ['GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL']
    url = make_url(raw)
    assert url.host == '127.0.0.1' and url.database.startswith('gaitlogic_test_')
    engine = create_engine(url, hide_parameters=True)
    settings = get_settings().model_copy(update={'security_rate_limits': {'coach_day': 5}})
    accepted = 0
    for _ in range(5):
        try:
            admission.consume(sessionmaker(engine), [('coach_day', subject)], settings=settings)
            accepted += 1
        except TooManyRequestsError:
            pass
    queue.put(accepted)
    engine.dispose()


def test_two_processes_share_one_budget(engine):
    context = multiprocessing.get_context('spawn')
    queue, subject = context.Queue(), uuid4().hex
    processes = [context.Process(target=process_consume, args=(subject, queue)) for _ in range(2)]
    for process in processes:
        process.start()
    try:
        outcomes = [queue.get(timeout=45) for _ in processes]
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        assert sum(outcomes) == 5
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
        queue.close()


def test_concurrent_leases_release_expire_and_late_owner_cannot_release_new_owner(engine):
    factory, subject = sessionmaker(engine), uuid4().hex
    now = datetime.utcnow().replace(microsecond=0)
    first = admission.acquire(factory, [(subject, 1)], now=now)
    with pytest.raises(TooManyRequestsError):
        admission.acquire(factory, [(subject, 1)], now=now)
    later = now+timedelta(seconds=get_settings().security_lease_seconds+1)
    second = admission.acquire(factory, [(subject, 1)], now=later)
    admission.release(factory, first)
    with factory() as db:
        assert db.get(SecurityRequestLease, second[0]) is not None
    admission.release(factory, second)


def build_app(engine):
    app = FastAPI()
    app.state.security_session_factory = sessionmaker(engine)
    app.add_middleware(SecurityMiddleware)
    app.add_exception_handler(AppError, app_error_handler)
    return app


def test_login_guard_is_shared_and_returns_retry_after_not_raw_account(sample, engine, monkeypatch):
    from server.api.routes.auth import router
    from server.api.deps import get_db
    db, users, *_ = sample
    monkeypatch.setenv('SECURITY_RATE_LIMITS', '{"login_pair":1}')
    get_settings.cache_clear()
    app = build_app(engine)
    app.include_router(router, prefix='/api')
    def session():
        with sessionmaker(engine)() as value:
            yield value
    app.dependency_overrides[get_db] = session
    client = TestClient(app)
    credentials = {'username': users[0].username, 'password': 'synthetic-wrong-password'}
    assert client.post('/api/auth/login', json=credentials).status_code == 401
    response = client.post('/api/auth/login', json=credentials)
    assert response.status_code == 429 and int(response.headers['Retry-After']) > 0
    assert users[0].username not in response.text
    with sessionmaker(engine)() as check:
        assert len(check.scalars(select(SecurityRateBucket).where(SecurityRateBucket.key_hash == admission.opaque_key('login_account', f'user:{users[0].id}'))).all()) == 1


def test_token_boundary_and_disabled_user_checked_before_ai_admission(sample, engine):
    from server.api.deps import get_current_user, get_db
    from server.services.auth_service import create_access_token, create_mcp_access_token
    db, users, *_ = sample
    app = build_app(engine)
    def session():
        with sessionmaker(engine)() as value:
            yield value
    app.dependency_overrides[get_db] = session
    @app.post('/api/ai-plan/generate')
    def endpoint(user=Depends(get_current_user)):
        pytest.fail('Unauthorized user reached generator')
    client = TestClient(app)
    mcp = create_mcp_access_token(users[0])
    assert client.post('/api/ai-plan/generate', json={}, headers={'Authorization': f'Bearer {mcp}'}).status_code == 401
    web = create_access_token(users[0])
    users[0].status = 'disabled'
    db.commit()
    assert client.post('/api/ai-plan/generate', json={}, headers={'Authorization': f'Bearer {web}'}).status_code == 401
    with sessionmaker(engine)() as check:
        assert check.get(SecurityRateBucket, admission.opaque_key('plan_day', f'user:{users[0].id}')) is None


def test_lease_renewal_preserves_live_owner(engine):
    factory = sessionmaker(engine)
    tokens = admission.acquire(factory, [(uuid4().hex, 1)], now=datetime.utcnow()-timedelta(seconds=30))
    with factory() as db:
        before = db.get(SecurityRequestLease, tokens[0]).expires_at
    admission.renew(factory, tokens)
    with factory() as db:
        assert db.get(SecurityRequestLease, tokens[0]).expires_at > before
    admission.release(factory, tokens)


def test_cancellation_releases_ai_lease(engine):
    import asyncio
    import httpx
    from fastapi import Request
    factory = sessionmaker(engine)
    app = build_app(engine)
    async def execute():
        started = asyncio.Event()
        @app.post('/api/coach/query')
        async def endpoint(request: Request):
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(admission.user_admission, request, uuid4().int % 1000000000)
            started.set()
            await asyncio.Event().wait()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
            task = asyncio.create_task(client.post('/api/coach/query', json={}))
            await asyncio.wait_for(started.wait(), timeout=10)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(SecurityRequestLease)) == 0
    asyncio.run(execute())


def test_mcp_recovery_permission_and_knowledge_budget_before_handler(sample, engine, monkeypatch):
    from starlette.responses import JSONResponse
    from server.mcp.http import McpHttpDependencies, McpHttpSecurityMiddleware
    from server.services.auth_service import create_mcp_access_token
    from planner_core.database.models import McpOAuthGrant
    db, users, *_ = sample
    settings = get_settings().model_copy(update={'mcp_oauth_enabled': True, 'security_rate_limits': {'knowledge': 1}})
    resource = settings.mcp_resource_uri or settings.mcp_public_base_url.rstrip('/')+'/mcp'
    grant_id = uuid4().hex
    db.add(McpOAuthGrant(grant_id=grant_id, client_id='synthetic-client', user_id=users[0].id, resource_uri=resource))
    db.commit()
    called = []
    async def handler(scope, receive, send):
        called.append(True)
        await JSONResponse({'ok': True})(scope, receive, send)
    middleware = McpHttpSecurityMiddleware(handler, McpHttpDependencies(settings=settings, session_factory=sessionmaker(engine)))
    client = TestClient(middleware)
    basic = create_mcp_access_token(users[0], grant_id=grant_id)
    headers = {'Authorization': f'Bearer {basic}'}
    rpc = lambda name: {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': {}}}
    denied = client.post('/mcp', headers=headers, json=rpc('get_recovery_trend'))
    assert denied.status_code == 403 and not called
    assert client.post('/mcp', headers=headers, json=rpc('retrieve_training_knowledge')).status_code == 200
    denied = client.post('/mcp', headers=headers, json=rpc('retrieve_training_knowledge'))
    assert denied.status_code == 429 and int(denied.headers['Retry-After']) > 0 and len(called) == 1
    full = create_mcp_access_token(users[0], grant_id=grant_id, scopes=['mcp:read', 'mcp:recovery:read'])
    assert client.post('/mcp', headers={'Authorization': f'Bearer {full}'}, json=rpc('get_recovery_trend')).status_code == 200


def test_ai_concurrency_rejects_before_work_and_releases_on_error(sample, engine):
    from server.api.deps import get_current_user, get_db
    from server.services.auth_service import create_access_token
    db, users, *_ = sample
    app = build_app(engine)
    def session():
        with sessionmaker(engine)() as value:
            yield value
    app.dependency_overrides[get_db] = session
    started, finish = Event(), Event()
    @app.post('/api/coach/query')
    def work(user=Depends(get_current_user)):
        started.set()
        assert finish.wait(10)
        raise RuntimeError('synthetic failure')
    client = TestClient(app, raise_server_exceptions=False)
    headers = {'Authorization': f'Bearer {create_access_token(users[0])}'}
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, '/api/coach/query', headers=headers, json={})
        try:
            assert started.wait(10)
            denied = client.post('/api/coach/query', headers=headers, json={})
            assert denied.status_code == 429 and denied.json()['code'] == 'CONCURRENCY_LIMITED'
        finally:
            finish.set()
        assert pending.result(timeout=15).status_code == 500
    with sessionmaker(engine)() as check:
        assert check.scalar(select(func.count()).select_from(SecurityRequestLease)) == 0


def test_admin_allowlist_does_not_trust_forwarded_headers(engine, monkeypatch):
    monkeypatch.setenv('SECURITY_ADMIN_ALLOWED_IPS', '192.0.2.1/32')
    get_settings.cache_clear()
    app = build_app(engine)
    @app.get('/api/admin/test')
    def endpoint():
        pytest.fail('Denied source must never reach handler')
    response = TestClient(app).get('/api/admin/test', headers={'X-Forwarded-For': '192.0.2.1'})
    assert response.status_code == 403


def test_chunked_body_limit_before_parser_and_storage_outage_fails_closed(engine, monkeypatch):
    monkeypatch.setenv('SECURITY_REQUEST_MAX_BYTES', '1024')
    get_settings.cache_clear()
    app = build_app(engine)
    @app.post('/api/body')
    def endpoint(payload: dict):
        pytest.fail('Oversized body reached handler')
    client = TestClient(app)
    response = client.post('/api/body', content=iter([b'x'*700, b'x'*700]))
    assert response.status_code == 413
    from unittest.mock import Mock
    app.state.security_session_factory = Mock(side_effect=RuntimeError('PRIVATE_CANARY'))
    failed = client.post('/api/body', json={})
    assert failed.status_code == 503 and 'PRIVATE_CANARY' not in failed.text
    @app.get('/api/health')
    def health():
        return {'status': 'ok'}
    assert client.get('/api/health').status_code == 200


def test_migration_partial_retry_idempotency_and_expired_cleanup(engine):
    from scripts.upgrade_security_hardening_v1 import upgrade, prune
    with engine.begin() as db:
        SecurityRequestLease.__table__.drop(db, checkfirst=True)
        upgrade(db)
        upgrade(db)
        assert inspect(db).has_table('security_rate_bucket')
        assert inspect(db).has_table('security_request_lease')
        old_key, live_key = uuid4().hex*2, uuid4().hex*2
        db.execute(SecurityRateBucket.__table__.insert(), [
            {'key_hash': old_key, 'count': 1, 'expires_at': datetime.utcnow()-timedelta(days=2)},
            {'key_hash': live_key, 'count': 1, 'expires_at': datetime.utcnow()-timedelta(days=2)}])
        db.execute(SecurityRequestLease.__table__.insert().values(token='synthetic-live', gate_hash=live_key,
            expires_at=datetime.utcnow()+timedelta(minutes=5)))
        prune(db)
        assert db.scalar(select(SecurityRateBucket.key_hash).where(SecurityRateBucket.key_hash == old_key)) is None
        assert db.scalar(select(SecurityRateBucket.key_hash).where(SecurityRateBucket.key_hash == live_key)) == live_key
