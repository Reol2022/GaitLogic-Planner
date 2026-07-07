from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from planner_core.config import get_settings
from server.common.exceptions import BadRequestError, ServiceUnavailableError

ENCRYPTION_ALGORITHM = "AES-256-GCM"


def _decode_key(raw_key: str | None) -> bytes:
    if not raw_key:
        raise ServiceUnavailableError(
            "Garmin 令牌加密密钥未配置。",
            error_code="TOKEN_ENCRYPTION_KEY_MISSING",
        )
    text = raw_key.strip()
    for candidate in (text, text + "=" * (-len(text) % 4)):
        try:
            decoded = base64.urlsafe_b64decode(candidate.encode("ascii"))
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
    raw = text.encode("utf-8")
    if len(raw) == 32:
        return raw
    if len(raw) > 32:
        return hashlib.sha256(raw).digest()
    raise ServiceUnavailableError(
        "Garmin 令牌加密密钥长度不足。",
        error_code="TOKEN_ENCRYPTION_KEY_INVALID",
    )


def encrypt_token_payload(payload: dict[str, Any]) -> str:
    settings = get_settings()
    key = _decode_key(settings.garmin_token_encryption_key)
    nonce = os.urandom(12)
    plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    envelope = {
        "alg": ENCRYPTION_ALGORITHM,
        "key_version": settings.garmin_token_key_version,
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
        "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
    }
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decrypt_token_payload(encrypted_payload: str | None) -> dict[str, Any]:
    if not encrypted_payload:
        raise BadRequestError("Garmin 连接需要重新认证。", error_code="REAUTHENTICATION_REQUIRED")
    settings = get_settings()
    key = _decode_key(settings.garmin_token_encryption_key)
    try:
        envelope = json.loads(encrypted_payload)
        nonce = base64.urlsafe_b64decode(envelope["nonce"])
        ciphertext = base64.urlsafe_b64decode(envelope["ciphertext"])
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        decoded = json.loads(plaintext.decode("utf-8"))
    except (KeyError, ValueError, TypeError, InvalidTag) as exc:
        raise BadRequestError("Garmin 令牌解密失败，请重新连接。", error_code="TOKEN_DECRYPTION_FAILED") from exc
    if not isinstance(decoded, dict):
        raise BadRequestError("Garmin 令牌格式无效，请重新连接。", error_code="TOKEN_DECRYPTION_FAILED")
    return decoded
