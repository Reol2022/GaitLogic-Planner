from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

FACTS_SCHEMA_VERSION = "1.0.0"
SOURCE_VERSION = "v0.10.1"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def decimal_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def date_text(value: date | None) -> str | None:
    return value.isoformat() if value else None


def enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def base_facts() -> dict[str, Any]:
    return {
        "athlete": {},
        "plan": {},
        "planned_workout": {},
        "previous_day": {},
        "recent_training": {},
        "recovery": {},
        "workout": {},
        "weekly": {},
        "race": {},
        "system": {
            "facts_schema_version": FACTS_SCHEMA_VERSION,
            "generated_at": now_iso(),
            "source_version": SOURCE_VERSION,
        },
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def hash_facts(facts: dict[str, Any]) -> str:
    stable = dict(facts)
    system = dict(stable.get("system") or {})
    system.pop("generated_at", None)
    stable["system"] = system
    return hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()


def workout_type_bucket(raw: str | None) -> str:
    value = (raw or "unknown").lower()
    if value in {"interval_speed", "interval", "i", "repetition", "r", "tempo", "threshold", "t1", "t2"}:
        return "key"
    if value in {"long_run", "lsd"}:
        return "long_run"
    if value == "rest":
        return "rest"
    if value in {"easy", "recovery", "easy_with_speed"}:
        return "easy"
    return "unknown"


def is_high_intensity(raw: str | None) -> bool:
    return workout_type_bucket(raw) == "key"

