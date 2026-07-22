from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from planner_core.database.models import RunnerStateSnapshotRecord
from planner_core.enums import RunnerStateAutoSnapshotStatus


class RunnerStateSnapshotDuplicateReason(str, Enum):
    PAYLOAD_HASH = "PAYLOAD_HASH"


@dataclass(frozen=True)
class RunnerStateSnapshotCreationResult:
    snapshot: RunnerStateSnapshotRecord
    created: bool
    duplicate_reason: RunnerStateSnapshotDuplicateReason | None = None


@dataclass(frozen=True)
class RunnerStateAutoSnapshotResult:
    status: RunnerStateAutoSnapshotStatus
    receipt_id: int | None
    snapshot_id: int | None
    trigger_reference: str
    error_code: str | None = None
