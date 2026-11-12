"""Opt-in MySQL OAuth security integration with synthetic accounts only."""
from __future__ import annotations

import base64
import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from planner_core.config import get_settings
from planner_core.database.models import McpOAuthAuthorizationCode, McpOAuthClient, McpOAuthGrant, McpOAuthRefreshToken, UserAccount
from server.api.routes import mcp_oauth
from server.mcp.http import McpHttpDependencies, create_mcp_http_app
from server.services.auth_service import hash_password, decode_mcp_access_token, create_access_token


def test_two_user_oauth_token_rotation_and_revocation_on_isolated_mysql(monkeypatch):
    raw = os.getenv("GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("isolated MySQL test database is not configured")
    url = make_url(raw)
    if url.get_backend_name() != "mysql" or url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").startswith("gaitlogic_test_"):
        pytest.fail("Refusing non-local or non-test MySQL database")
    monkeypatch.setenv("MCP_HTTP_ENABLED", "true")
    monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
    monkeypatch.setenv("MCP_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("JWT_SECRET_KEY", "fictional-mcp-mysql-test-secret")
    get_settings.cache_clear()
    engine = create_engine(url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(mcp_oauth, "SessionLocal", factory)
    suffix = uuid.uuid4().hex[:12]
    names = [f"synthetic-mcp-a-{suffix}", f"synthetic-mcp-b-{suffix}"]
    client_ids: list[str] = []
    user_ids: list[int] = []
    password = "Synthetic-password-0123!"
    try:
        with factory.begin() as db:
            for name in names:
                user = UserAccount(username=name, password_hash=hash_password(password), status="active")
                db.add(user)
                db.flush()
                user_ids.append(user.id)
        app = create_mcp_http_app(dependencies=McpHttpDependencies(settings=get_settings(), session_factory=factory))
        from server.main import create_app
        from server.api.deps import get_db
        import server.mcp.http as http_module
        monkeypatch.setattr(http_module, "create_mcp_http_app", lambda: app)
        application = create_app()

        def test_db():
            with factory() as db:
                yield db

        application.dependency_overrides[get_db] = test_db
        with TestClient(application) as client:
            headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"}
            meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}, "io.modelcontextprotocol/clientInfo": {"name": "synthetic", "version": "1"}}
            tokens = []
            refreshes = []
            for user_index, name in enumerate(names):
                registration = client.post("/oauth/register", json={"redirect_uris": ["http://127.0.0.1/callback"]})
                assert registration.status_code == 201
                client_id = registration.json()["client_id"]
                client_ids.append(client_id)
                verifier = "v" * 43
                challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
                form = {"client_id": client_id, "redirect_uri": "http://127.0.0.1/callback", "resource": "http://127.0.0.1:8000/mcp", "code_challenge": challenge, "code_challenge_method": "S256", "scope": "mcp:read", "approve": "yes", "username": name, "password": password}
                if user_index == 1:
                    form['scope'] = 'mcp:read mcp:recovery:read'
                    without_consent = client.post('/oauth/authorize', data=form, follow_redirects=False)
                    assert without_consent.status_code == 200 and 'approve_recovery' in without_consent.text
                    form['approve_recovery'] = 'yes'
                authorized = client.post("/oauth/authorize", data=form, follow_redirects=False)
                assert authorized.status_code == 302
                code = parse_qs(urlparse(authorized.headers["location"]).query)["code"][0]
                wrong_resource = client.post("/oauth/token", data={"grant_type": "authorization_code", "client_id": client_id, "code": code, "redirect_uri": form["redirect_uri"], "code_verifier": verifier, "resource": "http://127.0.0.1:8000/wrong"})
                assert wrong_resource.status_code == 400
                assert wrong_resource.json()["error"] == "invalid_target"
                token = client.post("/oauth/token", data={"grant_type": "authorization_code", "client_id": client_id, "code": code, "redirect_uri": form["redirect_uri"], "code_verifier": verifier, "resource": form["resource"]})
                assert token.status_code == 200
                tokens.append(token.json()["access_token"])
                refreshes.append(token.json()["refresh_token"])
            assert [int(decode_mcp_access_token(token)["sub"]) for token in tokens] == user_ids
            assert 'mcp:recovery:read' not in decode_mcp_access_token(tokens[0])['scope'].split()
            assert 'mcp:recovery:read' in decode_mcp_access_token(tokens[1])['scope'].split()
            recovery_request = {'jsonrpc':'2.0', 'id':2, 'method':'tools/call', 'params':{'name':'get_recovery_trend', 'arguments':{'days':7}, '_meta':meta}}
            outcomes = []
            for index, access in enumerate(tokens):
                response = client.post('/mcp', headers={**headers, 'Mcp-Method':'tools/call', 'Mcp-Name':'get_recovery_trend', 'Authorization':'Bearer '+access}, json=recovery_request)
                assert response.status_code == (403 if index == 0 else 200)
                outcomes.append(response.json() if index == 0 else response.json()['result']['structuredContent'])
            assert outcomes[0]['code'] == 'INSUFFICIENT_PERMISSION'
            assert outcomes[1]['status'] == 'SUCCEEDED'
            # An older client requesting only base access can opt in on the
            # authorization page, but only through a new explicit consent.
            optional = {**form, 'client_id': client_ids[0], 'username': names[0],
                'scope': 'mcp:read', 'approve_recovery': 'yes'}
            approved = client.post('/oauth/authorize', data=optional, follow_redirects=False)
            assert approved.status_code == 302
            optional_code = parse_qs(urlparse(approved.headers['location']).query)['code'][0]
            upgraded = client.post('/oauth/token', data={'grant_type': 'authorization_code', 'client_id': client_ids[0],
                'code': optional_code, 'redirect_uri': optional['redirect_uri'], 'code_verifier': verifier, 'resource': optional['resource']})
            assert upgraded.status_code == 200
            assert 'mcp:recovery:read' in upgraded.json()['scope'].split()
            assert 'mcp:recovery:read' in decode_mcp_access_token(upgraded.json()['access_token'])['scope'].split()
            restored = client.post('/mcp', headers={**headers, 'Mcp-Method': 'tools/call', 'Mcp-Name': 'get_recovery_trend',
                'Authorization': 'Bearer ' + upgraded.json()['access_token']}, json=recovery_request)
            assert restored.status_code == 200 and restored.json()['result']['structuredContent']['status'] == 'SUCCEEDED'
            escalation = client.post('/oauth/token', data={'grant_type':'refresh_token', 'client_id':client_ids[0], 'refresh_token':refreshes[0], 'resource':form['resource'], 'scope':'mcp:read mcp:recovery:read'})
            assert escalation.status_code == 400 and escalation.json()['error'] == 'invalid_scope'
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta}}
            for token in tokens:
                assert client.post("/mcp", headers={**headers, "Authorization": "Bearer " + token}, json=request).status_code == 200
            refresh_data = {"grant_type": "refresh_token", "client_id": client_ids[0], "refresh_token": refreshes[0], "resource": "http://127.0.0.1:8000/mcp"}
            assert client.post("/oauth/token", data={**refresh_data, "resource": "http://127.0.0.1:8000/wrong"}).status_code == 400
            barrier = Barrier(3)

            def exchange(index):
                barrier.wait(timeout=10)
                data = refresh_data if index < 2 else {**refresh_data, "client_id": client_ids[1], "refresh_token": refreshes[1]}
                return client.post("/oauth/token", data=data)

            with ThreadPoolExecutor(max_workers=3) as pool:
                responses = list(pool.map(exchange, range(3)))
            assert sorted(response.status_code for response in responses[:2]) == [200, 400]
            assert responses[2].status_code == 200
            narrowed = client.post('/oauth/token', data={'grant_type':'refresh_token', 'client_id':client_ids[1], 'refresh_token':responses[2].json()['refresh_token'], 'resource':form['resource'], 'scope':'mcp:read'})
            assert narrowed.status_code == 200 and narrowed.json()['scope'] == 'mcp:read'
            assert decode_mcp_access_token(narrowed.json()['access_token'])['scope'] == 'mcp:read'
            reexpanded = client.post('/oauth/token', data={'grant_type':'refresh_token', 'client_id':client_ids[1], 'refresh_token':narrowed.json()['refresh_token'], 'resource':form['resource'], 'scope':'mcp:read mcp:recovery:read'})
            assert reexpanded.status_code == 400 and reexpanded.json()['error'] == 'invalid_scope'
            rotated_refresh = next(response.json()["refresh_token"] for response in responses[:2] if response.status_code == 200)
            assert client.post("/oauth/token", data={**refresh_data, "refresh_token": rotated_refresh}).status_code == 400
            assert client.post("/mcp", headers={**headers, "Authorization": "Bearer " + tokens[0]}, json=request).status_code == 401
            assert client.post("/mcp", headers={**headers, "Authorization": "Bearer " + tokens[1]}, json=request).status_code == 200
            with factory() as db:
                web_token = create_access_token(db.get(UserAccount, user_ids[0]))
            revoke = client.post(f"/api/mcp/authorizations/{client_ids[1]}/revoke", headers={"Authorization": "Bearer " + web_token})
            assert revoke.status_code == 200
            assert client.post("/mcp", headers={**headers, "Authorization": "Bearer " + tokens[1]}, json=request).status_code == 200
            assert client.post(f"/api/mcp/authorizations/{client_ids[0]}/revoke", headers={"Authorization": "Bearer " + web_token}).status_code == 200
    finally:
        with factory.begin() as db:
            for model in (McpOAuthAuthorizationCode, McpOAuthRefreshToken, McpOAuthGrant):
                if user_ids:
                    db.execute(delete(model).where(model.user_id.in_(user_ids)))
            if client_ids:
                db.execute(delete(McpOAuthClient).where(McpOAuthClient.client_id.in_(client_ids)))
            if user_ids:
                db.execute(delete(UserAccount).where(UserAccount.id.in_(user_ids)))
        engine.dispose()
        get_settings.cache_clear()
