from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
import json
import logging
import zipfile
import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from planner_core.config import get_settings
from planner_core.database.models import UserAccount
from server.common.exceptions import UnauthorizedError, BadRequestError, database_error_handler, unhandled_exception_handler
from server.services import auth_service as auth
from server.security import admission
from server.security.uploads import validate_xlsx, read_upload


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'synthetic-security-only-key')
    monkeypatch.setenv('SECURITY_CONTROLS_ENABLED', 'false')
    monkeypatch.setenv('WEB_TOKEN_LEGACY_UNTIL', '')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def user():
    return UserAccount(id=42, username='synthetic-runner', password_hash='not-a-login')


def test_web_and_mcp_tokens_are_separate_namespaces():
    web, mcp = auth.create_access_token(user()), auth.create_mcp_access_token(user())
    assert auth.decode_token(web)['purpose'] == 'web'
    assert auth.decode_mcp_access_token(mcp)['purpose'] == 'mcp'
    with pytest.raises(UnauthorizedError):
        auth.decode_token(mcp)
    with pytest.raises(auth.McpTokenValidationError):
        auth.decode_mcp_access_token(web)


@pytest.mark.parametrize('changes', [{'sub': 'x'}, {'sub': '-1'}, {'sub': '9'*100}, {'sub': True},
    {'sub': '\u0661'}, {'exp': True}, {'aud': 'mcp'}, {'scope': 'mcp:read'}, {'grant_id': 'synthetic'}])
def test_signed_but_invalid_web_claims_are_rejected(changes):
    payload = auth.decode_token(auth.create_access_token(user()))
    payload.update(changes)
    with pytest.raises(UnauthorizedError):
        auth.decode_token(auth._sign_jwt_payload(payload))


@pytest.mark.parametrize('token', ['invalid', 'e30.W10.invalid', 'x'*9000, 'W10.e30.x'])
def test_malformed_tokens_fail_without_internal_exception(token):
    with pytest.raises(UnauthorizedError):
        auth.decode_token(token)
    with pytest.raises(auth.McpTokenValidationError):
        auth.decode_mcp_access_token(token)


def test_legacy_compatibility_is_explicit_time_limited_and_never_accepts_mcp(monkeypatch):
    payload = {'sub': '42', 'exp': int((datetime.now(timezone.utc)+timedelta(hours=1)).timestamp())}
    token = auth._sign_jwt_payload(payload)
    with pytest.raises(UnauthorizedError):
        auth.decode_token(token)
    monkeypatch.setenv('WEB_TOKEN_LEGACY_UNTIL', (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    get_settings.cache_clear()
    assert auth.decode_token(token)['sub'] == '42'
    with pytest.raises(UnauthorizedError):
        auth.decode_token(auth.create_mcp_access_token(user()))


def request(ip, headers=None):
    return Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': headers or [], 'client': (ip, 1234)})


def test_forwarding_headers_cannot_spoof_admin_allowlist_or_rate_key():
    req = request('203.0.113.8', [(b'x-forwarded-for', b'127.0.0.1'), (b'x-real-ip', b'127.0.0.1')])
    assert admission.client_ip(req) == '203.0.113.8'
    assert not admission.admin_ip_allowed(req, '127.0.0.1/32')
    assert admission.admin_ip_allowed(req, '203.0.113.0/24')
    assert admission.ip_subject(request('2001:db8::123')) == '2001:db8::/64'


def test_exception_logs_and_validation_responses_omit_canaries(caplog):
    req = request('127.0.0.1')
    exc = OperationalError('INSERT PRIVATE_CANARY', {'password': 'PRIVATE_CANARY'}, Exception('PRIVATE_CANARY'))
    with caplog.at_level(logging.ERROR):
        response = asyncio.run(database_error_handler(req, exc))
        asyncio.run(unhandled_exception_handler(req, RuntimeError('PRIVATE_CANARY')))
    assert response.status_code == 503
    assert 'PRIVATE_CANARY' not in caplog.text
    app = FastAPI()
    from server.api.routes.auth import router
    from server.common.exceptions import validation_error_handler
    from fastapi.exceptions import RequestValidationError
    app.include_router(router, prefix='/api')
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    response = TestClient(app).post('/api/auth/login', json={'username': 'synthetic', 'password': 'PRIVATE_CANARY'*20})
    assert response.status_code == 400 and 'PRIVATE_CANARY' not in response.text


def archive(name, data):
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as value:
        value.writestr(name, data)
    return output.getvalue()


@pytest.mark.parametrize('name,data', [('xl/worksheets/sheet1.xml', b'0'*100000),
    ('../escape.xml', b'<x/>'), ('xl/vbaProject.bin', b'code'),
    ('xl/sharedStrings.xml', b'<!DOCTYPE a [<!ENTITY x "value">]><a/>'),
    ('xl/sharedStrings.xml', '<!DOCTYPE x><x/>'.encode('utf-16'))], ids=['ratio', 'path', 'macro', 'entity', 'utf16'])
def test_unsafe_archives_rejected_before_parser(name, data):
    with pytest.raises(BadRequestError):
        validate_xlsx(archive(name, data))


def test_standard_excel_template_is_accepted():
    from server.services.excel_template_service import generate_excel_template_bytes
    validate_xlsx(generate_excel_template_bytes())


def test_upload_read_is_bounded():
    from unittest.mock import AsyncMock
    file = SimpleNamespace(read=AsyncMock(return_value=b'x'*(2*1024*1024+1)))
    with pytest.raises(BadRequestError):
        asyncio.run(read_upload(file))
    file.read.assert_awaited_once_with(2*1024*1024+1)
