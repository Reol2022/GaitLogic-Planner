from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from sqlalchemy import inspect

from planner_core.database.models import WorkoutLog


def _normalized_decimal(value: Decimal | float | int | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).normalize()


def _normalized_enum(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


@dataclass(frozen=True)
class RunnerStateRelevantWorkoutLogProjection:
    """Stable projection of fields consumed by Runner State A/B."""

    planned_workout_id: int | None
    activity_date: date | None
    status_normalized: str | None
    workout_type: str | None
    actual_distance_km: Decimal | None
    actual_duration_seconds: int | None
    rpe: int | None
    avg_heart_rate: int | None
    max_heart_rate: int | None

    @classmethod
    def from_workout_log(cls, log: WorkoutLog) -> RunnerStateRelevantWorkoutLogProjection:
        return cls(
            planned_workout_id=int(log.planned_workout_id) if log.planned_workout_id is not None else None,
            activity_date=log.activity_date,
            status_normalized=_normalized_enum(log.status_normalized),
            workout_type=_normalized_enum(log.workout_type),
            actual_distance_km=_normalized_decimal(log.actual_distance_km),
            actual_duration_seconds=int(log.actual_duration_seconds) if log.actual_duration_seconds is not None else None,
            rpe=int(log.rpe) if log.rpe is not None else None,
            avg_heart_rate=int(log.avg_heart_rate) if log.avg_heart_rate is not None else None,
            max_heart_rate=int(log.max_heart_rate) if log.max_heart_rate is not None else None,
        )


@dataclass(frozen=True)
class MaterialChangeCounts:
    created_log_count: int = 0
    updated_log_count: int = 0

    @property
    def runner_state_affecting_change_count(self) -> int:
        return self.created_log_count + self.updated_log_count


@dataclass
class _TrackedWorkoutLog:
    log: WorkoutLog
    before: RunnerStateRelevantWorkoutLogProjection | None
    created: bool


class WorkoutLogMaterialChangeTracker:
    """Collect the first before-state and final after-state once per log."""

    def __init__(self) -> None:
        self._entries: dict[int, _TrackedWorkoutLog] = {}

    @staticmethod
    def _key(log: WorkoutLog) -> int:
        if log.id is None:
            raise ValueError("WorkoutLog must be flushed before material-change tracking")
        return int(log.id)

    def capture_before(self, log: WorkoutLog) -> None:
        key = self._key(log)
        self._entries.setdefault(
            key,
            _TrackedWorkoutLog(
                log=log,
                before=RunnerStateRelevantWorkoutLogProjection.from_workout_log(log),
                created=False,
            ),
        )

    def capture_created(self, log: WorkoutLog) -> None:
        key = self._key(log)
        self._entries[key] = _TrackedWorkoutLog(log=log, before=None, created=True)

    def merge(self, other: WorkoutLogMaterialChangeTracker) -> None:
        for key, incoming in other._entries.items():
            existing = self._entries.get(key)
            if existing is None:
                self._entries[key] = incoming
                continue
            existing.log = incoming.log
            if incoming.created:
                existing.created = True
                existing.before = None

    def counts(self) -> MaterialChangeCounts:
        created = 0
        updated = 0
        for entry in self._entries.values():
            state = inspect(entry.log)
            if state.deleted:
                continue
            if entry.created:
                created += 1
                continue
            after = RunnerStateRelevantWorkoutLogProjection.from_workout_log(entry.log)
            if entry.before != after:
                updated += 1
        return MaterialChangeCounts(created_log_count=created, updated_log_count=updated)

    def has_material_change(self) -> bool:
        return self.counts().runner_state_affecting_change_count > 0


@dataclass(frozen=True)
class GarminSyncRunOutcome:
    job_id: int
    user_id: int
    provider: str
    sync_run_id: str
    claimed: bool
    committed: bool
    final_status: str
    created_log_count: int = 0
    updated_log_count: int = 0
    unchanged_activity_count: int = 0
    runner_state_affecting_change_count: int = 0
    warning_codes: tuple[str, ...] = field(default_factory=tuple)
