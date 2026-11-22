"""Run with an explicitly provisioned restricted gaitlogic_test_* MySQL URL.

No production databases, Garmin requests, or paid LLM calls are permitted.
Raw artifacts and temporary synthetic tokens are ignored by Git.
"""
import json
import csv
import os
import socket
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.audit-private'


def test_isolated_read_baseline():
    url = make_url(os.environ['GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL'])
    assert url.host == '127.0.0.1' and url.port == 3307 and url.database.startswith('gaitlogic_test_')
    os.environ.update(JWT_SECRET_KEY='synthetic-audit-key-not-production', GARMIN_SMART_SYNC_ENABLED='false', AGENT_TRACING_ENABLED='false')
    from planner_core.config import get_settings
    get_settings.cache_clear()
    from planner_core.database.models import UserAccount, WorkoutLog, ExternalAccountConnection, ExternalActivity, ExternalActivityLap, DailyRecoveryCheckin, McpOAuthGrant
    from planner_core.enums import WorkoutStatusNormalized
    from server.services.auth_service import hash_password, create_access_token, create_mcp_access_token
    engine = create_engine(url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    today = date.today()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    os.environ.update(MCP_PUBLIC_BASE_URL=base, MCP_RESOURCE_URI=base + '/mcp')
    get_settings.cache_clear()
    accounts = []
    password = 'Synthetic-audit-only-password!'
    password_hash = hash_password(password)
    with factory.begin() as db:
        for i in range(50):
            user = UserAccount(username=f'audit_synthetic_{i}', password_hash=password_hash, status='active', role='admin' if i == 0 else 'user')
            db.add(user)
            db.flush()
            connection = ExternalAccountConnection(user_id=user.id)
            db.add(connection)
            db.flush()
            ref = None
            for day in range(84):
                when = today - timedelta(days=day)
                log = WorkoutLog(user_id=user.id, activity_date=when, actual_distance_km=10, actual_duration_seconds=3000, workout_type='easy', source_type='garmin', status_normalized=WorkoutStatusNormalized.completed_normal, is_unplanned=True)
                db.add(log)
                if day < 28:
                    db.flush()
                    activity = ExternalActivity(user_id=user.id, connection_id=connection.id, external_activity_id=f'audit-{i}-{day}', connector_version='synthetic', activity_type='running', start_time_local=datetime.combine(when, datetime.min.time()), activity_date=when, distance_m=10000, duration_seconds=3000, workout_log_id=log.id)
                    db.add(activity)
                    db.flush()
                    db.add_all([ExternalActivityLap(external_activity_id=activity.id, lap_index=k, distance_m=1000, duration_seconds=300) for k in range(1, 11)])
                    db.add(DailyRecoveryCheckin(user_id=user.id, checkin_date=when, sleep_duration_minutes=450, hrv_value=60, resting_heart_rate_bpm=50, device_provider='garmin', device_data_status='AVAILABLE', device_synced_at=datetime.now()))
                    if day == 0:
                        ref = f'workout_log:{log.id}'
            grant_id = f'audit-grant-{i}'
            db.add(McpOAuthGrant(grant_id=grant_id, client_id='synthetic-audit-client', user_id=user.id, resource_uri=base + '/mcp'))
            accounts.append(dict(username=user.username, user_id=user.id, month=today.strftime('%Y-%m'), web_token=create_access_token(user), mcp_token=create_mcp_access_token(user, grant_id=grant_id, scopes=['mcp:read', 'mcp:recovery:read']), record_ref=ref))
    account_file = OUT / 'lab-users.json'
    account_file.write_text(json.dumps(accounts), encoding='utf-8')
    env = os.environ.copy()
    env.update(MCP_HTTP_ENABLED='true', MCP_OAUTH_ENABLED='true', MCP_ALLOWED_HOSTS=f'127.0.0.1:{port}', PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1', GAITLOGIC_AUDIT_USERS_FILE=str(account_file))
    process = None
    results = dict(data_scale={'users': 50, 'workout_logs': 4200, 'activities': 1400, 'laps': 14000, 'recovery_days': 1400}, sequential=[], loads=[])
    log_file = (OUT / 'lab-server.log').open('w', encoding='utf-8')
    try:
        process = subprocess.Popen([sys.executable, '-B', '-m', 'uvicorn', 'scripts.audit.lab_app:app', '--host', '127.0.0.1', '--port', str(port), '--log-level', 'error', '--no-access-log'], cwd=ROOT, env=env, stdout=log_file, stderr=log_file)
        with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
            for _ in range(150):
                assert process.poll() is None, 'isolated server exited; inspect private log'
                try:
                    if client.get('/api/health').status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError('isolated server readiness timeout')
            # Measure real login cost, not a mock credential verifier.
            endpoints = [('/api/auth/login', None), ('/api/dashboard', None), ('/api/dashboard/today', None), ('/api/training-calendar', {'month': accounts[1]['month']}), ('/api/runner-state/current', None), ('/api/ai-plan/context', None), ('/api/admin/console/overview', None)]
            for endpoint, params in endpoints:
                samples, statuses = [], []
                for _ in range(12):
                    start = time.perf_counter()
                    token = accounts[0 if '/admin/' in endpoint else 1]['web_token']
                    r = client.post(endpoint, json={'username': accounts[1]['username'], 'password': password}) if endpoint.endswith('/login') else client.get(endpoint, params=params, headers={'Authorization': 'Bearer ' + token})
                    samples.append((time.perf_counter() - start) * 1000)
                    statuses.append(r.status_code)
                results['sequential'].append(dict(endpoint=endpoint, samples_ms=samples, statuses=statuses))
            # Actual boundary check: no user may fetch another user's detail via MCP.
            from server.mcp.adapters import McpToolAdapter
            from server.mcp.context import McpExecutionContext, McpRequestIdentity
            adapter = McpToolAdapter(McpExecutionContext(identity_provider=lambda: McpRequestIdentity(accounts[1]['user_id'], frozenset({'mcp:read', 'mcp:recovery:read'})), session_factory=factory))
            assert adapter.get_training_detail(record_ref=accounts[2]['record_ref']).status == 'FAILED'
            assert adapter.get_training_detail(record_ref=accounts[1]['record_ref']).status == 'SUCCEEDED'
            assert adapter.get_recovery_trend(days=14).status == 'SUCCEEDED'
            results['isolation_checks'] = '3 passed (adapter + real MySQL)'
        # Query timings/counts and EXPLAIN on the actual shared Training Service.
        from server.services.training_load_service import get_recent_training_read
        statements = []
        @event.listens_for(engine, 'before_cursor_execute')
        def count_sql(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                statements.append((statement, parameters))
        with factory() as db:
            started = time.perf_counter()
            value = get_recent_training_read(db, user_id=accounts[1]['user_id'], days=28, limit=20)
            results['training_query'] = dict(duration_ms=(time.perf_counter()-started)*1000, select_count=len(statements), total_sessions=value.total_sessions)
            captured = list(statements)
            explains = []
            for statement, params in captured[:8]:
                with engine.connect() as connection:
                    explains.append([dict(r) for r in connection.exec_driver_sql('EXPLAIN ' + statement, params).mappings()])
            (OUT / 'explain.json').write_text(json.dumps(explains, default=str, indent=2), encoding='utf-8')
        # Tool environment is independent of the application's Python dependencies.
        sys.path.append(str(OUT / 'tools/Lib/site-packages'))
        import psutil
        launcher = psutil.Process(process.pid)
        descendants = launcher.children(recursive=True)
        monitored = max([launcher, *descendants], key=lambda p: p.memory_info().rss)
        for users, duration in [(1, 15), (5, 15), (10, 15), (20, 15), (10, 60), (50, 45)]:
            prefix = OUT / f'final-load-{users}-{duration}'
            before_cpu = sum(monitored.cpu_times()[:2])
            before = time.perf_counter()
            with (OUT / f'final-locust-{users}-{duration}.log').open('w', encoding='utf-8') as output:
                job = subprocess.Popen([str(OUT / 'tools/Scripts/python.exe'), '-m', 'locust', '-f', 'scripts/audit/locustfile.py', '--headless', '--host', base, '-u', str(users), '-r', str(users), '-t', f'{duration}s', '--csv', str(prefix), '--only-summary', '--exit-code-on-error', '2'], cwd=ROOT, env=env, stdout=output, stderr=output)
                rss = []
                while job.poll() is None:
                    rss.append(monitored.memory_info().rss)
                    time.sleep(0.5)
                elapsed = time.perf_counter() - before
                with Path(str(prefix) + '_stats.csv').open(encoding='utf-8') as stats:
                    aggregate = next(r for r in csv.DictReader(stats) if r['Name'] == 'Aggregated')
                assert int(aggregate['Request Count']) > 0, 'zero requests is NOT a valid baseline'
                results['loads'].append(dict(users=users, duration_seconds=duration, elapsed_seconds=elapsed, exit_code=job.returncode, cpu_one_core_percent=(sum(monitored.cpu_times()[:2])-before_cpu)/elapsed*100, max_rss_mb=max(rss)/1024**2, aggregate=aggregate))
                (OUT / 'performance.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print('AUDIT baseline artifacts recorded; load return codes:', [r['exit_code'] for r in results['loads']])
    finally:
        if process is not None:
            if os.name == 'nt' and process.poll() is None:
                # Windows venv launcher can own the actual interpreter as a child.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log_file.close()
        account_file.unlink(missing_ok=True)
        engine.dispose()
