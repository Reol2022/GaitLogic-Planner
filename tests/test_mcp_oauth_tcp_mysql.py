"""Opt-in loopback TCP OAuth/MCP test against an isolated MySQL database."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from planner_core.database.base import Base
from planner_core.database.models import McpOAuthAuthorizationCode, McpOAuthClient, McpOAuthGrant, McpOAuthRefreshToken, UserAccount, WorkoutLog
from planner_core.enums import WorkoutStatusNormalized
from server.services.auth_service import hash_password
from server.services.training_load_service import get_recent_training_read


def test_real_tcp_two_user_training_isolation_and_revoke():
    raw = os.getenv("GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("isolated MySQL test database is not configured")
    url = make_url(raw)
    if url.get_backend_name() != "mysql" or url.host not in {"127.0.0.1", "localhost"} or not (url.database == "gaitlogic_test_mcp" or (url.database or "").startswith("gaitlogic_test_mcp_migration_")):
        pytest.fail("TCP test requires an explicitly isolated local MCP test database")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:12]
    usernames = [f"tcp-mcp-a-{suffix}", f"tcp-mcp-b-{suffix}"]
    password = "Fictional-oauth-test-password!"
    user_ids, client_ids, refs = [], [], []
    process = None
    second_process = None
    try:
        with factory.begin() as db:
            for index, name in enumerate(usernames):
                user = UserAccount(username=name, password_hash=hash_password(password), status="active")
                db.add(user)
                db.flush()
                user_ids.append(user.id)
                own_refs = []
                for day in range(22 if index == 0 else 1):
                    log = WorkoutLog(user_id=user.id, activity_date=date.today()-timedelta(days=day), status_normalized=WorkoutStatusNormalized.completed_normal, actual_distance_km=8 + index, actual_duration_seconds=3000, workout_type="easy", source_type="garmin" if index == 0 else "manual", is_unplanned=True)
                    db.add(log)
                    db.flush()
                    own_refs.append(f"workout_log:{log.id}")
                refs.append(set(own_refs))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update({"MYSQL_HOST": "127.0.0.1", "MYSQL_PORT": str(url.port or 3306), "MYSQL_USER": url.username or "", "MYSQL_PASSWORD": url.password or "", "MYSQL_DATABASE": url.database, "JWT_SECRET_KEY": "fictional-tcp-oauth-secret", "MCP_HTTP_ENABLED": "true", "MCP_OAUTH_ENABLED": "true", "MCP_PUBLIC_BASE_URL": base, "MCP_RESOURCE_URI": base + "/mcp", "MCP_ALLOWED_HOSTS": f"127.0.0.1:{port}", "MCP_OAUTH_ALLOWED_REDIRECT_HOSTS": "127.0.0.1", "PYTHONDONTWRITEBYTECODE": "1"})
        process = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with httpx.Client(timeout=10, trust_env=False) as client:
            for _ in range(100):
                if process.poll() is not None:
                    pytest.fail("synthetic server exited before readiness")
                try:
                    if client.get(base + "/api/health").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                pytest.fail("synthetic server failed readiness")
            tokens, refresh_tokens = [], []
            for username in usernames:
                registration = client.post(base + "/oauth/register", json={"redirect_uris": ["http://127.0.0.1/callback"]})
                assert registration.status_code == 201
                client_id = registration.json()["client_id"]
                client_ids.append(client_id)
                verifier = "v" * 43
                challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
                form = {"client_id": client_id, "redirect_uri": "http://127.0.0.1/callback", "resource": base + "/mcp", "code_challenge": challenge, "code_challenge_method": "S256", "scope": "mcp:read", "approve": "yes", "username": username, "password": password}
                auth = client.post(base + "/oauth/authorize", data=form, follow_redirects=False)
                assert auth.status_code == 302
                code = parse_qs(urlparse(auth.headers["location"]).query)["code"][0]
                mismatch = client.post(base + "/oauth/token", data={"grant_type": "authorization_code", "client_id": client_id, "code": code, "redirect_uri": form["redirect_uri"], "code_verifier": verifier, "resource": base + "/wrong"})
                assert mismatch.status_code == 400
                exchanged = client.post(base + "/oauth/token", data={"grant_type": "authorization_code", "client_id": client_id, "code": code, "redirect_uri": form["redirect_uri"], "code_verifier": verifier, "resource": form["resource"]})
                assert exchanged.status_code == 200
                assert client.post(base + "/oauth/token", data={"grant_type": "authorization_code", "client_id": client_id, "code": code, "redirect_uri": form["redirect_uri"], "code_verifier": verifier, "resource": form["resource"]}).status_code == 400
                tokens.append(exchanged.json()["access_token"])
                refresh_tokens.append(exchanged.json()["refresh_token"])

            meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}, "io.modelcontextprotocol/clientInfo": {"name": "synthetic-tcp", "version": "1"}}
            for token in tokens:
                listed = client.post(base + "/mcp", headers={"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"}, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta}})
                assert listed.status_code == 200
                assert any(item["name"] == "get_recent_training" for item in listed.json()["result"]["tools"])
            with socket.socket() as second_socket:
                second_socket.bind(("127.0.0.1", 0))
                second_port = second_socket.getsockname()[1]
            second_base = f"http://127.0.0.1:{second_port}"
            second_env = {**env, "MCP_RESOURCE_URI": second_base + "/mcp", "MCP_ALLOWED_HOSTS": f"127.0.0.1:{second_port}"}
            second_process = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(second_port), "--log-level", "error"], env=second_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                if second_process.poll() is not None:
                    pytest.fail("second synthetic resource exited before readiness")
                try:
                    if client.get(second_base + "/api/health").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                pytest.fail("second synthetic resource failed readiness")
            replay = client.post(second_base + "/mcp", headers={"Authorization": "Bearer " + tokens[0], "Accept": "application/json, text/event-stream", "X-Forwarded-Host": f"127.0.0.1:{port}"}, json={})
            assert replay.status_code == 401
            cross_refresh = client.post(second_base + "/oauth/token", data={"grant_type": "refresh_token", "client_id": client_ids[0], "refresh_token": refresh_tokens[0], "resource": second_base + "/mcp"})
            assert cross_refresh.status_code == 400
            metadata = client.get(base + "/.well-known/oauth-protected-resource/mcp", headers={"Host": "attacker.invalid", "X-Forwarded-Host": "attacker.invalid"})
            assert metadata.status_code == 200 and metadata.json()["resource"] == base + "/mcp"
            def b64(value):
                return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
            legacy_header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
            legacy_payload = b64(json.dumps({"sub": str(user_ids[0]), "iss": base + "/oauth", "aud": base + "/mcp", "scope": "mcp:read", "purpose": "mcp", "exp": int(time.time()) + 600}, separators=(",", ":")).encode())
            legacy_body = legacy_header + "." + legacy_payload
            legacy = legacy_body + "." + b64(hmac.new(b"fictional-tcp-oauth-secret", legacy_body.encode(), hashlib.sha256).digest())
            assert client.post(base + "/mcp", headers={"Authorization": "Bearer " + legacy, "Accept": "application/json, text/event-stream"}, json={}).status_code == 401
            previous_payload = b64(json.dumps({"sub": str(user_ids[0]), "iss": "gaitlogic-planner", "aud": "gaitlogic-mcp", "purpose": "mcp", "exp": int(time.time()) + 600}, separators=(",", ":")).encode())
            previous_body = legacy_header + "." + previous_payload
            previous_token = previous_body + "." + b64(hmac.new(b"fictional-tcp-oauth-secret", previous_body.encode(), hashlib.sha256).digest())
            assert client.post(base + "/mcp", headers={"Authorization": "Bearer " + previous_token, "Accept": "application/json, text/event-stream"}, json={}).status_code == 401
            legacy_refresh = "fictional-legacy-refresh"
            with factory.begin() as db:
                db.add(McpOAuthRefreshToken(token_hash=hashlib.sha256(legacy_refresh.encode()).hexdigest(), client_id=client_ids[0], user_id=user_ids[0], scopes_json=["mcp:read"], expires_at=datetime.utcnow() + timedelta(hours=1)))
            legacy_exchange = client.post(base + "/oauth/token", data={"grant_type": "refresh_token", "client_id": client_ids[0], "refresh_token": legacy_refresh, "resource": base + "/mcp"})
            assert legacy_exchange.status_code == 400
            invalid = client.post(base + "/mcp", headers={"Authorization": "Bearer " + tokens[0], "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "get_recent_training"}, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_recent_training", "arguments": {"days": 7, "user_id": user_ids[1]}, "_meta": meta}})
            assert invalid.status_code == 200 and invalid.json()["result"]["isError"] is True
            durations = []

            def call(index, days):
                started = time.perf_counter()
                headers = {"Authorization": "Bearer " + tokens[index], "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "get_recent_training"}
                response = httpx.post(base + "/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_recent_training", "arguments": {"days": days, "limit": 20}, "_meta": meta}}, timeout=20, trust_env=False)
                assert response.status_code == 200
                result = response.json()["result"]["structuredContent"]
                assert result["status"] == "SUCCEEDED"
                durations.append((time.perf_counter() - started) * 1000)
                return result["data"]
            with ThreadPoolExecutor(max_workers=2) as pool:
                a, b = list(pool.map(lambda i: call(i, 28), (0, 1)))
            assert {item["record_ref"] for item in a["items"]}.issubset(refs[0])
            assert {item["record_ref"] for item in b["items"]} == refs[1]
            assert len(a["items"]) == 20 and a["details_complete"] is False
            assert a["summary"]["total_sessions"] == 22
            assert len(call(0, 7)["items"]) == 7
            assert all(item["source"] == "GARMIN" for item in a["items"])
            with factory() as db:
                direct = get_recent_training_read(db, user_id=user_ids[0], days=28, limit=20)
                direct_by_ref = {item.record_ref: item for item in direct.items}
                assert direct.total_sessions == a["summary"]["total_sessions"]
                for item in a["items"]:
                    expected = direct_by_ref[item["record_ref"]]
                    assert item["date"] == expected.date.isoformat()
                    assert item["source"] == expected.source
                    assert item["distance_km"] == expected.distance_km
                    assert item["duration_seconds"] == expected.duration_seconds
            for _ in range(20):
                assert {item["record_ref"] for item in call(1, 7)["items"]} == refs[1]
            with ThreadPoolExecutor(max_workers=10) as pool:
                concurrent = list(pool.map(lambda i: call(i % 2, 7), range(10)))
            for index, data in enumerate(concurrent):
                assert {item["record_ref"] for item in data["items"]}.issubset(refs[index % 2])
            measured = sorted(durations)
            print(f"synthetic TCP tool calls={len(measured)} p50_ms={measured[len(measured)//2]:.2f} p95_ms={measured[int((len(measured)-1)*0.95)]:.2f}")
            login = client.post(base + "/api/auth/login", json={"username": usernames[0], "password": password})
            assert login.status_code == 200
            revoked = client.post(base + f"/api/mcp/authorizations/{client_ids[0]}/revoke", headers={"Authorization": "Bearer " + login.json()["access_token"]})
            assert revoked.status_code == 200
            rejected = client.post(base + "/mcp", headers={"Authorization": "Bearer " + tokens[0], "Accept": "application/json, text/event-stream"}, json={})
            assert rejected.status_code == 401
            assert {item["record_ref"] for item in call(1, 7)["items"]} == refs[1]
            process.terminate()
            process.wait(timeout=10)
            process = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                if process.poll() is not None:
                    pytest.fail("synthetic server exited during restart")
                try:
                    if client.get(base + "/api/health").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                pytest.fail("synthetic server failed readiness after restart")
            assert client.post(base + "/mcp", headers={"Authorization": "Bearer " + tokens[0], "Accept": "application/json, text/event-stream"}, json={}).status_code == 401
            assert {item["record_ref"] for item in call(1, 7)["items"]} == refs[1]
    finally:
        if second_process is not None:
            second_process.terminate()
            try:
                second_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                second_process.kill()
                second_process.wait(timeout=5)
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        with factory.begin() as db:
            if user_ids:
                for model in (McpOAuthAuthorizationCode, McpOAuthRefreshToken, McpOAuthGrant, WorkoutLog):
                    db.execute(delete(model).where(model.user_id.in_(user_ids)))
            if client_ids:
                db.execute(delete(McpOAuthClient).where(McpOAuthClient.client_id.in_(client_ids)))
            if user_ids:
                db.execute(delete(UserAccount).where(UserAccount.id.in_(user_ids)))
        engine.dispose()
