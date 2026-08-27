"""OAuth 2.1 endpoints for the remote, read-only GaitLogic MCP resource."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import html
import secrets
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.models import (
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthRefreshToken,
    UserAccount,
)
from planner_core.database.session import SessionLocal
from server.services.auth_service import create_mcp_access_token, verify_password


router = APIRouter(tags=["mcp oauth"])
_SCOPE = "mcp:read"
_CODE_TTL_MINUTES = 5


def _base_url() -> str:
    return get_settings().mcp_public_base_url.rstrip("/")


def _enabled() -> bool:
    return get_settings().mcp_http_enabled and get_settings().mcp_oauth_enabled


def _oauth_error(error: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error})


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_challenge(verifier: str) -> str:
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
    warning = f"<p>{html.escape(message)}</p>" if message else ""
    body = f"""<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>授权 GaitLogic MCP</title>
    <body><main><h1>授权 GaitLogic MCP</h1><p>登录后，ChatGPT 将只读访问你的训练计划、训练记录、Runner State 和训练知识引用。</p>{warning}
    <form method=\"post\" action=\"/oauth/authorize\">{fields}
    <label>用户名 <input name=\"username\" autocomplete=\"username\" required></label><br>
    <label>密码 <input type=\"password\" name=\"password\" autocomplete=\"current-password\" required></label><br>
    <label><input type=\"checkbox\" name=\"approve\" value=\"yes\" required> 我同意授予只读访问权限</label><br>
    <button type=\"submit\">登录并授权</button></form></main></body></html>"""
    return HTMLResponse(body)


@router.get("/.well-known/oauth-authorization-server")
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
        "scopes_supported": [_SCOPE],
    }


@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata():
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    return {
        "resource": f"{_base_url()}/mcp",
        "authorization_servers": [f"{_base_url()}/oauth"],
        "scopes_supported": [_SCOPE],
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
    with SessionLocal.begin() as db:
        db.add(McpOAuthClient(client_id=client_id, client_name=str(payload.get("client_name") or "")[:255] or None, redirect_uris_json=redirect_uris, scopes_json=[_SCOPE]))
    return JSONResponse(status_code=201, content={"client_id": client_id, "redirect_uris": redirect_uris, "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "none"})


@router.get("/oauth/authorize")
def authorize_form(request: Request):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    params = _params(request)
    if params.get("response_type") != "code" or params.get("code_challenge_method") != "S256":
        return _oauth_error("invalid_request")
    with SessionLocal() as db:
        client = db.scalar(select(McpOAuthClient).where(McpOAuthClient.client_id == params.get("client_id")))
        if client is None or params.get("redirect_uri") not in (client.redirect_uris_json or []):
            return _oauth_error("invalid_request")
    if params.get("scope", _SCOPE) != _SCOPE or not params.get("code_challenge"):
        return _oauth_error("invalid_scope")
    return _login_page(params)


@router.post("/oauth/authorize")
async def authorize_submit(request: Request):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    params = await _form_params(request)
    if params.get("approve") != "yes":
        return _login_page(params, "必须确认授权。")
    with SessionLocal.begin() as db:
        client = db.scalar(select(McpOAuthClient).where(McpOAuthClient.client_id == params.get("client_id")))
        user = db.scalar(select(UserAccount).where(UserAccount.username == params.get("username")))
        if client is None or params.get("redirect_uri") not in (client.redirect_uris_json or []) or user is None or user.status != "active" or not verify_password(params.get("password", ""), user.password_hash):
            return _login_page(params, "用户名、密码或授权请求无效。")
        if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
            return _login_page(params, "授权请求缺少 PKCE 校验。")
        code = secrets.token_urlsafe(32)
        db.add(McpOAuthAuthorizationCode(code_hash=_hash(code), client_id=client.client_id, user_id=user.id, redirect_uri=params["redirect_uri"], code_challenge=params["code_challenge"], scopes_json=[_SCOPE], expires_at=datetime.utcnow() + timedelta(minutes=_CODE_TTL_MINUTES)))
    query = {"code": code}
    if params.get("state"):
        query["state"] = params["state"]
    return RedirectResponse(f"{params['redirect_uri']}?{urlencode(query)}", status_code=302)


@router.post("/oauth/token")
async def token(request: Request):
    if not _enabled():
        return _oauth_error("temporarily_unavailable", 404)
    params = await _form_params(request)
    grant_type, client_id = params.get("grant_type"), params.get("client_id")
    with SessionLocal.begin() as db:
        client = db.scalar(select(McpOAuthClient).where(McpOAuthClient.client_id == client_id))
        if client is None:
            return _oauth_error("invalid_client", 401)
        if grant_type == "authorization_code":
            record = db.scalar(select(McpOAuthAuthorizationCode).where(McpOAuthAuthorizationCode.code_hash == _hash(params.get("code", ""))).with_for_update())
            if record is None or record.client_id != client_id or record.consumed_at is not None or record.expires_at < datetime.utcnow() or record.redirect_uri != params.get("redirect_uri") or _pkce_challenge(params.get("code_verifier", "")) != record.code_challenge:
                return _oauth_error("invalid_grant")
            record.consumed_at = datetime.utcnow()
            user = db.get(UserAccount, record.user_id)
            scopes = record.scopes_json
        elif grant_type == "refresh_token":
            record = db.scalar(select(McpOAuthRefreshToken).where(McpOAuthRefreshToken.token_hash == _hash(params.get("refresh_token", ""))).with_for_update())
            if record is None or record.client_id != client_id or record.revoked_at is not None or record.expires_at < datetime.utcnow():
                return _oauth_error("invalid_grant")
            record.revoked_at = datetime.utcnow()
            user = db.get(UserAccount, record.user_id)
            scopes = record.scopes_json
        else:
            return _oauth_error("unsupported_grant_type")
        if user is None or user.status != "active":
            return _oauth_error("invalid_grant")
        refresh_token = secrets.token_urlsafe(48)
        db.add(McpOAuthRefreshToken(token_hash=_hash(refresh_token), client_id=client_id, user_id=user.id, scopes_json=scopes, expires_at=datetime.utcnow() + timedelta(days=get_settings().mcp_oauth_refresh_token_expire_days)))
        access_token = create_mcp_access_token(user)
    return {"access_token": access_token, "token_type": "Bearer", "expires_in": get_settings().mcp_token_expire_minutes * 60, "refresh_token": refresh_token, "scope": " ".join(scopes)}
