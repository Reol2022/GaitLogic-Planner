from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import secrets

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.models import UserAccount
from server.common.exceptions import BadRequestError, UnauthorizedError
from server.schemas.auth import TokenResponse, UserLogin, UserRegister

JWT_ALGORITHM = "HS256"
PASSWORD_ITERATIONS = 260_000
MCP_TOKEN_PURPOSE = "mcp"


class McpTokenValidationError(ValueError):
    """Safe classification for a token that cannot authenticate an MCP request."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${b64url_encode(digest)}"


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        scheme, iterations_text, salt, expected = hashed_password.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_text),
        )
        return hmac.compare_digest(b64url_encode(digest), expected)
    except (ValueError, TypeError):
        return False


def get_user_by_username(db: Session, username: str) -> UserAccount | None:
    return db.scalar(select(UserAccount).where(UserAccount.username == username))


def register_user(db: Session, payload: UserRegister) -> UserAccount:
    conditions = [UserAccount.username == payload.username]
    if payload.email:
        conditions.append(UserAccount.email == payload.email)
    existing = db.scalar(select(UserAccount).where(or_(*conditions)))
    if existing is not None:
        if existing.username == payload.username:
            raise BadRequestError("Username already exists.")
        raise BadRequestError("Email already exists.")

    user = UserAccount(
        username=payload.username,
        email=payload.email,
        nickname=payload.nickname,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def signing_key() -> bytes:
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise BadRequestError("JWT_SECRET_KEY is not configured.")
    return settings.jwt_secret_key.encode("utf-8")


def create_access_token(user: UserAccount) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    header = {"typ": "JWT", "alg": JWT_ALGORITHM}
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.access_token_expire_days)).timestamp()),
    }
    header_part = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(signing_key(), message, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{b64url_encode(signature)}"


def _sign_jwt_payload(payload: dict) -> str:
    header = {"typ": "JWT", "alg": JWT_ALGORITHM}
    header_part = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(signing_key(), message, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{b64url_encode(signature)}"


def create_mcp_access_token(user: UserAccount) -> str:
    """Issue a short-lived JWT that is bound only to the MCP resource server."""

    settings = get_settings()
    now = datetime.now(timezone.utc)
    return _sign_jwt_payload(
        {
            "sub": str(user.id),
            "iss": settings.mcp_token_issuer,
            "aud": settings.mcp_token_audience,
            "purpose": MCP_TOKEN_PURPOSE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=settings.mcp_token_expire_minutes)).timestamp()),
        }
    )


def decode_mcp_access_token(token: str) -> dict:
    """Validate a GaitLogic MCP token without accepting the web JWT namespace."""

    try:
        header_part, payload_part, signature_part = token.split(".", 2)
        header = json.loads(b64url_decode(header_part))
        if header.get("typ") != "JWT" or header.get("alg") != JWT_ALGORITHM:
            raise McpTokenValidationError("INVALID_TOKEN")
        message = f"{header_part}.{payload_part}".encode("ascii")
        expected_signature = hmac.new(signing_key(), message, hashlib.sha256).digest()
        if not hmac.compare_digest(b64url_encode(expected_signature), signature_part):
            raise McpTokenValidationError("INVALID_TOKEN")
        payload = json.loads(b64url_decode(payload_part))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise McpTokenValidationError("TOKEN_EXPIRED")
        settings = get_settings()
        if payload.get("iss") != settings.mcp_token_issuer:
            raise McpTokenValidationError("INVALID_TOKEN")
        if payload.get("aud") != settings.mcp_token_audience:
            raise McpTokenValidationError("INVALID_TOKEN")
        if payload.get("purpose") != MCP_TOKEN_PURPOSE:
            raise McpTokenValidationError("INVALID_TOKEN")
        if int(payload.get("sub", 0)) <= 0:
            raise McpTokenValidationError("INVALID_TOKEN")
        return payload
    except McpTokenValidationError:
        raise
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise McpTokenValidationError("INVALID_TOKEN") from exc


def authenticate_user(db: Session, payload: UserLogin) -> TokenResponse:
    user = get_user_by_username(db, payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid username or password.")
    if user.status != "active":
        raise UnauthorizedError("User account is not active.")

    user.last_login_at = datetime.now()
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user))


def decode_token(token: str) -> dict:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
        message = f"{header_part}.{payload_part}".encode("ascii")
        expected_signature = hmac.new(signing_key(), message, hashlib.sha256).digest()
        if not hmac.compare_digest(b64url_encode(expected_signature), signature_part):
            raise UnauthorizedError("Invalid or expired token.")
        payload = json.loads(b64url_decode(payload_part))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise UnauthorizedError("Invalid or expired token.")
        return payload
    except (ValueError, json.JSONDecodeError) as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc
