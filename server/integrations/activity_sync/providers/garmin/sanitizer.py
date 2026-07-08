from __future__ import annotations

SENSITIVE_KEYS = {
    "email",
    "username",
    "displayName",
    "ownerDisplayName",
    "userProfileId",
    "profileId",
    "access_token",
    "refresh_token",
}


def sanitize_garmin_payload(payload: dict) -> dict:
    sanitized: dict = {}
    for key, value in payload.items():
        if key in SENSITIVE_KEYS:
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_garmin_payload(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_garmin_payload(item) if isinstance(item, dict) else item for item in value]
        else:
            sanitized[key] = value
    return sanitized
