"""OAuth 2.1 endpoints for the remote, read-only GaitLogic MCP resource."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import html
import re
import secrets
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.models import (
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthRefreshToken,
    McpOAuthGrant,
    UserAccount,
)
from planner_core.database.session import SessionLocal
from server.services.auth_service import create_mcp_access_token, verify_password
from server.api.deps import get_current_user


router = APIRouter(tags=["mcp oauth"])
_SCOPE = "mcp:read"
_RECOVERY_SCOPE = "mcp:recovery:read"


def _requested_scopes(params: dict[str, str]) -> list[str] | None:
    scopes = params.get("scope", _SCOPE).split()
    if _SCOPE not in scopes or not set(scopes) <= {_SCOPE, _RECOVERY_SCOPE}:
        return None
    return sorted(set(scopes))
_CODE_TTL_MINUTES = 5


def _base_url() -> str:
    return get_settings().mcp_public_base_url.rstrip("/")


def _resource() -> str:
    return get_settings().mcp_resource_uri or f"{_base_url()}/mcp"


def _enabled() -> bool:
    return get_settings().mcp_http_enabled and get_settings().mcp_oauth_enabled


def _oauth_error(error: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error})


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_challenge(verifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
        return ""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _allowed_redirect_uri(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return False
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        return False
    allowed = {item.strip().lower() for item in get_settings().mcp_oauth_allowed_redirect_hosts.split(",") if item.strip()}
    host = (parsed.hostname or "").lower()
    return host in allowed or any(host.endswith("." + item) for item in allowed)


def _params(request: Request) -> dict[str, str]:
    values = {key: value[-1] for key, value in parse_qs(request.url.query, keep_blank_values=True).items()}
    return values


async def _form_params(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8")
    return {key: value[-1] for key, value in parse_qs(raw, keep_blank_values=True).items()}


def _login_page(params: dict[str, str], message: str | None = None) -> HTMLResponse:
    fields = "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value)}">'
        for key, value in params.items()
        if key in {"client_id", "redirect_uri", "state", "scope", "code_challenge", "code_challenge_method", "resource"}
    )
    warning = f'<div class="notice" role="alert">{html.escape(message)}</div>' if message else ""
    recovery_consent = ('<label class="consent"><input type="checkbox" name="approve_recovery" value="yes" required><span>另外授权读取恢复历史：睡眠、HRV、静息心率及主观疲劳等。仅用于本应用的只读分析。</span></label>' if _RECOVERY_SCOPE in (_requested_scopes(params) or []) else '')
    body = f"""<!doctype html>
    <html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex, nofollow"><title>授权连接 · GaitLogic</title>
    <style>
    *{{box-sizing:border-box}} body{{margin:0;background:#f3f6f4;color:#1c3027;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.6}}
    .page{{min-height:100vh;display:grid;place-items:center;padding:32px 18px;background:radial-gradient(ellipse at 15% 0%,#dcefe4,transparent 40%),radial-gradient(ellipse at 100% 100%,#e0ece7,transparent 35%)}}
    .card{{width:min(100%,490px);background:#fff;border:1px solid #e2ebe5;border-radius:22px;box-shadow:0 20px 60px rgba(24,62,43,.09);padding:36px}}
    .brand{{display:flex;align-items:center;gap:11px;font-size:15px;font-weight:750;letter-spacing:.04em;color:#246445}}
    .mark{{display:grid;place-items:center;width:36px;height:36px;border-radius:11px;background:#226a48;color:white;font-size:18px}}
    .eyebrow{{display:inline-block;margin-top:29px;padding:4px 10px;border-radius:20px;background:#eaf5ed;color:#397855;font-size:12px;font-weight:700}}
    h1{{font-size:26px;line-height:1.3;margin:14px 0 8px;letter-spacing:-.02em}} .intro{{margin:0;color:#667a6e;font-size:14px}}
    .permissions{{margin:22px 0;padding:16px 18px;border-radius:14px;background:#f5f8f6;border:1px solid #e7eeea}}
    .permissions h2{{font-size:13px;margin:0 0 8px;color:#355444}} .permissions ul{{margin:0;padding-left:19px;color:#526b5b;font-size:13px}} .permissions li+li{{margin-top:3px}}
    .notice{{margin:16px 0;color:#a6352b;background:#fff3f0;border:1px solid #f5d4cd;border-radius:10px;padding:10px 12px;font-size:13px}}
    .field{{display:block;margin:16px 0 0;font-size:13px;font-weight:650;color:#385144}} .field input{{display:block;width:100%;margin-top:6px;padding:12px 13px;border:1px solid #d8e3db;border-radius:10px;font:inherit;font-size:14px;background:#fff;color:#1c3027;outline:none}}
    .field input:focus{{border-color:#438d63;box-shadow:0 0 0 3px rgba(67,141,99,.14)}} .consent{{display:flex;align-items:flex-start;gap:10px;margin:20px 0;color:#53695a;font-size:13px;cursor:pointer}}
    .consent input{{margin:4px 0 0;accent-color:#26744d;flex:none}} button{{width:100%;border:0;border-radius:11px;background:#246e49;color:white;font:inherit;font-weight:700;padding:13px;cursor:pointer}} button:hover{{background:#1c5e3d}} button:focus-visible{{outline:3px solid #91c5a5;outline-offset:3px}}
    .foot{{margin:18px 0 0;text-align:center;color:#829287;font-size:12px}} @media(max-width:480px){{.page{{padding:16px}} .card{{padding:26px 22px;border-radius:18px}} h1{{font-size:23px}}}}
    </style></head><body><main class="page"><section class="card" aria-labelledby="title">
    <div class="brand"><span class="mark" aria-hidden="true">G</span><span>GAITLOGIC</span></div>
    <span class="eyebrow">安全连接 · 只读授权</span><h1 id="title">连接 GaitLogic</h1>
    <p class="intro">登录你的 GaitLogic 账号，授权应用读取训练信息，用于提供更贴合你的分析。</p>
    <div class="permissions"><h2>授权后可读取</h2><ul><li>训练计划与训练记录</li><li>Runner State 与训练知识引用</li></ul></div>
    {warning}<form method="post" action="/oauth/authorize">{fields}
    <label class="field">用户名<input name="username" autocomplete="username" required></label>
    <label class="field">密码<input type="password" name="password" autocomplete="current-password" required></label>
    <label class="consent"><input type="checkbox" name="approve" value="yes" required><span>我已了解并同意授予上述只读访问权限。</span></label>
    {recovery_consent}<button type="submit">登录并授权</button></form>
    <p class="foot">请输入 GaitLogic 账号，并确认当前页面地址可信。</p>
    </section></main></body></html>"""
    return HTMLResponse(body)


@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/oauth")
def oauth_metadata():
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    issuer = f"{_base_url()}/oauth"
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "registration_endpoint": f"{issuer}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": [_SCOPE, _RECOVERY_SCOPE],
    }


@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata():
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    return {
        "resource": _resource(),
        "authorization_servers": [f"{_base_url()}/oauth"],
        "scopes_supported": [_SCOPE, _RECOVERY_SCOPE],
        "bearer_methods_supported": ["header"],
    }


@router.post("/oauth/register")
async def register_client(request: Request):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    try:
        payload = await request.json()
        redirect_uris = payload["redirect_uris"]
    except Exception:
        return _oauth_error("invalid_client_metadata")
    if not isinstance(redirect_uris, list) or not redirect_uris or not all(isinstance(uri, str) and _allowed_redirect_uri(uri) for uri in redirect_uris):
        return _oauth_error("invalid_redirect_uri")
    client_id = secrets.token_urlsafe(32)
    scope_text = payload.get('scope', _SCOPE)
    if not isinstance(scope_text, str):
        return _oauth_error('invalid_scope')
    scopes = _requested_scopes({'scope':scope_text})
    if scopes is None:
        return _oauth_error('invalid_scope')
    with SessionLocal.begin() as db:
        db.add(McpOAuthClient(client_id=client_id, client_name=str(payload.get("client_name") or "")[:255] or None, redirect_uris_json=redirect_uris, scopes_json=scopes))
    return JSONResponse(status_code=201, content={"client_id": client_id, "redirect_uris": redirect_uris, "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "none"})


@router.get("/oauth/authorize")
def authorize_form(request: Request):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    params = _params(request)
    if params.get("resource") != _resource():
        return _oauth_error("invalid_target")
    if _requested_scopes(params) is None:
        return _oauth_error("invalid_scope")
    if params.get("response_type") != "code" or params.get("code_challenge_method") != "S256":
        return _oauth_error("invalid_request")
    with SessionLocal() as db:
        client = db.scalar(select(McpOAuthClient).where(McpOAuthClient.client_id == params.get("client_id")))
        if client is None or params.get("redirect_uri") not in (client.redirect_uris_json or []):
            return _oauth_error("invalid_request")
    if _requested_scopes(params) is None or not params.get("code_challenge"):
        return _oauth_error("invalid_scope")
    return _login_page(params)


@router.post("/oauth/authorize")
async def authorize_submit(request: Request):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    params = await _form_params(request)
    if params.get("resource") != _resource():
        return _oauth_error("invalid_target")
    if _requested_scopes(params) is None:
        return _oauth_error("invalid_scope")
    if params.get("approve") != "yes":
        return _login_page(params, "必须确认授权。")
    if _RECOVERY_SCOPE in (_requested_scopes(params) or []) and params.get("approve_recovery") != "yes":
        return _login_page(params, "请单独确认恢复数据授权，或移除该权限后重新发起授权。")
    with SessionLocal.begin() as db:
        client = db.scalar(select(McpOAuthClient).where(McpOAuthClient.client_id == params.get("client_id")))
        user = db.scalar(select(UserAccount).where(UserAccount.username == params.get("username")))
        if client is None or params.get("redirect_uri") not in (client.redirect_uris_json or []) or user is None or user.status != "active" or not verify_password(params.get("password", ""), user.password_hash):
            return _login_page(params, "用户名、密码或授权请求无效。")
        if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
            return _login_page(params, "授权请求缺少 PKCE 校验。")
        code = secrets.token_urlsafe(32)
        grant_id = secrets.token_urlsafe(32)
        db.add(McpOAuthGrant(grant_id=grant_id, client_id=client.client_id, user_id=user.id, resource_uri=params["resource"]))
        db.add(McpOAuthAuthorizationCode(code_hash=_hash(code), client_id=client.client_id, user_id=user.id, redirect_uri=params["redirect_uri"], code_challenge=params["code_challenge"], resource_uri=params["resource"], grant_id=grant_id, scopes_json=_requested_scopes(params), expires_at=datetime.utcnow() + timedelta(minutes=_CODE_TTL_MINUTES)))
    query = {"code": code}
    if params.get("state"):
        query["state"] = params["state"]
    return RedirectResponse(f"{params['redirect_uri']}?{urlencode(query)}", status_code=302)


@router.post("/oauth/token")
async def token(request: Request):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    params = await _form_params(request)
    if params.get("resource") != _resource():
        return _oauth_error("invalid_target")
    grant_type, client_id = params.get("grant_type"), params.get("client_id")
    with SessionLocal.begin() as db:
        client = db.scalar(select(McpOAuthClient).where(McpOAuthClient.client_id == client_id))
        if client is None:
            return _oauth_error("invalid_client", 401)
        if grant_type == "authorization_code":
            record = db.scalar(select(McpOAuthAuthorizationCode).where(McpOAuthAuthorizationCode.code_hash == _hash(params.get("code", ""))).with_for_update())
            if record is None or record.resource_uri != params["resource"] or record.client_id != client_id or record.consumed_at is not None or record.expires_at < datetime.utcnow() or record.redirect_uri != params.get("redirect_uri") or _pkce_challenge(params.get("code_verifier", "")) != record.code_challenge:
                return _oauth_error("invalid_grant")
            record.consumed_at = datetime.utcnow()
            user = db.get(UserAccount, record.user_id)
            scopes = record.scopes_json
            grant_id = record.grant_id
        elif grant_type == "refresh_token":
            record = db.scalar(select(McpOAuthRefreshToken).where(McpOAuthRefreshToken.token_hash == _hash(params.get("refresh_token", ""))).with_for_update())
            if record is None or record.resource_uri != params["resource"] or record.client_id != client_id or record.expires_at < datetime.utcnow():
                return _oauth_error("invalid_grant")
            if record.revoked_at is not None:
                compromised = db.scalar(select(McpOAuthGrant).where(McpOAuthGrant.grant_id == record.grant_id).with_for_update())
                if compromised is not None and compromised.revoked_at is None:
                    compromised.revoked_at = datetime.utcnow()
                return _oauth_error("invalid_grant")
            record.revoked_at = datetime.utcnow()
            user = db.get(UserAccount, record.user_id)
            scopes = record.scopes_json
            grant_id = record.grant_id
        else:
            return _oauth_error("unsupported_grant_type")
        if user is None or user.status != "active":
            return _oauth_error("invalid_grant")
        grant = db.scalar(select(McpOAuthGrant).where(McpOAuthGrant.grant_id == grant_id).with_for_update())
        if grant is None or grant.revoked_at is not None or grant.user_id != user.id or grant.client_id != client_id or grant.resource_uri != params["resource"]:
            return _oauth_error("invalid_grant")
        requested = _requested_scopes(params) if 'scope' in params else scopes
        if not scopes or _SCOPE not in scopes or not set(scopes) <= {_SCOPE, _RECOVERY_SCOPE} or requested is None or not set(requested) <= set(scopes):
            db.rollback()
            return _oauth_error("invalid_scope")
        scopes = requested
        refresh_token = secrets.token_urlsafe(48)
        db.add(McpOAuthRefreshToken(token_hash=_hash(refresh_token), client_id=client_id, user_id=user.id, resource_uri=params["resource"], grant_id=grant_id, scopes_json=scopes, expires_at=datetime.utcnow() + timedelta(days=get_settings().mcp_oauth_refresh_token_expire_days)))
        access_token = create_mcp_access_token(user, grant_id=grant_id, scopes=scopes)
    return {"access_token": access_token, "token_type": "Bearer", "expires_in": get_settings().mcp_token_expire_minutes * 60, "refresh_token": refresh_token, "scope": " ".join(scopes)}


@router.get("/api/mcp/authorizations")
def list_authorizations(user: UserAccount = Depends(get_current_user)):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    with SessionLocal() as db:
        grants = db.scalars(select(McpOAuthGrant).where(McpOAuthGrant.user_id == user.id, McpOAuthGrant.revoked_at.is_(None))).all()
        client_ids = sorted({grant.client_id for grant in grants})
        clients = db.scalars(select(McpOAuthClient).where(McpOAuthClient.client_id.in_(client_ids))).all() if client_ids else []
        names = {client.client_id: client.client_name for client in clients}
        return {"clients": [{"client_id": client_id, "client_name": names.get(client_id)} for client_id in client_ids]}


@router.post("/api/mcp/authorizations/{client_id}/revoke")
def revoke_authorization(client_id: str, user: UserAccount = Depends(get_current_user)):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    with SessionLocal.begin() as db:
        grants = db.scalars(select(McpOAuthGrant).where(McpOAuthGrant.user_id == user.id, McpOAuthGrant.client_id == client_id).with_for_update()).all()
        for grant in grants:
            if grant.revoked_at is None:
                grant.revoked_at = datetime.utcnow()
    return {"revoked": True}
