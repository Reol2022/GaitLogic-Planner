"""Small privacy-first in-memory session fact store.

It stores summaries only. Raw tool payloads, prompts, knowledge chunks and
identity data are intentionally not accepted by this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any


_FORBIDDEN = {"token", "password", "authorization", "cookie", "prompt", "response", "email", "phone", "latitude", "longitude", "raw"}


@dataclass(frozen=True)
class SessionFact:
    key: str
    value: dict[str, Any]
    source: str
    collected_at: datetime
    expires_at: datetime

    @property
    def fresh(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at


class InMemorySessionFactStore:
    def __init__(self) -> None:
        self._facts: dict[tuple[int, str, str], SessionFact] = {}
        self._lock = RLock()

    @staticmethod
    def _safe(value: dict[str, Any]) -> bool:
        return all(str(key).lower() not in _FORBIDDEN and isinstance(item, (str, int, float, bool, type(None))) for key, item in value.items())

    def put(self, *, user_id: int, session_id: str, key: str, value: dict[str, Any], source: str, ttl: timedelta) -> None:
        if not self._safe(value):
            raise ValueError("session facts must be concise safe scalar summaries")
        now = datetime.now(timezone.utc)
        with self._lock:
            self._facts[(user_id, session_id, key)] = SessionFact(key, value, source, now, now + ttl)

    def get(self, *, user_id: int, session_id: str, key: str) -> SessionFact | None:
        with self._lock:
            fact = self._facts.get((user_id, session_id, key))
            if fact is None or not fact.fresh:
                self._facts.pop((user_id, session_id, key), None)
                return None
            return fact

    def invalidate(self, *, user_id: int, keys: set[str]) -> int:
        with self._lock:
            targets = [item for item in self._facts if item[0] == user_id and item[2] in keys]
            for item in targets:
                self._facts.pop(item, None)
            return len(targets)


SESSION_FACTS = InMemorySessionFactStore()

GARMIN_SYNC_INVALIDATES = {"runner_state", "weekly_mileage", "recent_training", "training_compliance", "recovery"}
LOG_MUTATION_INVALIDATES = {"runner_state", "weekly_summary", "weekly_mileage", "recent_training"}
PLAN_MUTATION_INVALIDATES = {"current_plan", "next_workout", "weekly_plan"}
