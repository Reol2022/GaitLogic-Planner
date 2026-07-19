from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json
import math
from typing import Any

from pydantic import BaseModel

from server.schemas.runner_state import RunnerStateSnapshot

RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION = "runner-state-snapshot-1.0.0"


def serialize_runner_state_snapshot(snapshot: RunnerStateSnapshot) -> dict[str, Any]:
    """Return the complete state as JSON-compatible data without mutating it."""
    return snapshot.model_dump(mode="json")


def _normalize_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Runner-state snapshot numbers must be finite.")
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize_json_value(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return _normalize_json_value(value.value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _normalize_decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Runner-state snapshot numbers must be finite.")
        return value
    if isinstance(value, dict):
        return {str(key): _normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported runner-state snapshot value: {type(value).__name__}")


def canonicalize_runner_state_payload(payload: Any) -> str:
    normalized = _normalize_json_value(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _semantic_payload_copy(payload: dict[str, Any]) -> dict[str, Any]:
    semantic = deepcopy(payload)

    def remove_nonsemantic_timestamps(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("calculated_at", None)
            value.pop("created_at", None)
            for item in value.values():
                remove_nonsemantic_timestamps(item)
        elif isinstance(value, list):
            for item in value:
                remove_nonsemantic_timestamps(item)

    remove_nonsemantic_timestamps(semantic)
    identity = semantic.get("identity")
    if isinstance(identity, dict):
        # RunnerStateSnapshot calls the calculation timestamp generated_at.
        # It is the same non-semantic audit time stored in record.calculated_at.
        identity.pop("generated_at", None)
    return semantic


def calculate_runner_state_payload_hash(
    payload: dict[str, Any],
    *,
    data_cutoff_date: date,
    ruleset_version: str,
    snapshot_schema_version: str = RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION,
) -> str:
    hash_input = {
        "data_cutoff_date": data_cutoff_date,
        "ruleset_version": ruleset_version,
        "snapshot_schema_version": snapshot_schema_version,
        "snapshot_payload": _semantic_payload_copy(payload),
    }
    canonical = canonicalize_runner_state_payload(hash_input)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
