from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only

from planner_core.database.models import RunnerStateSnapshotRecord, UserAccount
from planner_core.enums import RunnerStateSnapshotTriggerType
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.runner_state import RunnerStateSnapshot
from server.schemas.runner_state_snapshot import (
    RunnerStateSnapshotCreateResult,
    RunnerStateSnapshotDetail,
    RunnerStateSnapshotListItem,
    RunnerStateSnapshotListResponse,
)
from server.services.runner_state_service import RunnerStateService
from server.services.runner_state_snapshot_serializer import (
    RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION,
    calculate_runner_state_payload_hash,
    serialize_runner_state_snapshot,
)
from server.services.weekly_review_stats_service import APP_TIMEZONE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SaveOutcome:
    record: RunnerStateSnapshotRecord
    created: bool
    duplicate: bool


class RunnerStateSnapshotService:
    def __init__(
        self,
        db: Session,
        *,
        runner_state_service: RunnerStateService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.runner_state_service = runner_state_service or RunnerStateService(db)
        self.clock = clock or (lambda: datetime.now(APP_TIMEZONE))

    def save_current(self, current_user: UserAccount) -> RunnerStateSnapshotCreateResult:
        snapshot = self.runner_state_service.get_current(current_user)
        outcome = self._save_snapshot(user_id=int(current_user.id), snapshot=snapshot)
        logger.info(
            "Runner-state snapshot save completed id=%s user_id=%s trigger=%s "
            "ruleset=%s created=%s duplicate=%s",
            outcome.record.id,
            current_user.id,
            outcome.record.trigger_type.value,
            outcome.record.ruleset_version,
            outcome.created,
            outcome.duplicate,
        )
        return RunnerStateSnapshotCreateResult(
            snapshot=self._to_detail(outcome.record),
            created=outcome.created,
            duplicate=outcome.duplicate,
        )

    def _save_snapshot(self, *, user_id: int, snapshot: RunnerStateSnapshot) -> _SaveOutcome:
        payload = serialize_runner_state_snapshot(snapshot)
        cutoff = snapshot.identity.calculation_window_end
        calculated_at = (
            snapshot.inference_metadata.calculated_at
            if snapshot.inference_metadata is not None
            else snapshot.identity.generated_at
        )
        ruleset_version = self._ruleset_version(snapshot)
        payload_hash = calculate_runner_state_payload_hash(
            payload,
            data_cutoff_date=cutoff,
            ruleset_version=ruleset_version,
        )
        existing = self._find_duplicate(user_id, cutoff, payload_hash)
        if existing is not None:
            return _SaveOutcome(record=existing, created=False, duplicate=True)

        now = self._business_now()
        record = RunnerStateSnapshotRecord(
            user_id=user_id,
            snapshot_date=now.date(),
            data_cutoff_date=cutoff,
            calculated_at=self._to_database_datetime(calculated_at),
            created_at=self._to_database_datetime(now),
            trigger_type=RunnerStateSnapshotTriggerType.MANUAL,
            trigger_reference=None,
            snapshot_schema_version=RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION,
            ruleset_version=ruleset_version,
            distance_7d_km=self._decimal(snapshot.recent_training.distance_7d_km),
            distance_28d_km=self._decimal(snapshot.recent_training.distance_28d_km),
            volume_trend=self._enum_value(snapshot.volume_trend.state) if snapshot.volume_trend else None,
            training_consistency=(
                self._enum_value(snapshot.training_consistency.state)
                if snapshot.training_consistency
                else None
            ),
            fatigue_state=self._enum_value(snapshot.fatigue.state) if snapshot.fatigue else None,
            training_phase=self._enum_value(snapshot.inferred_state.training_phase),
            risk_flag_count=len(snapshot.risk_flags),
            evidence_coverage=(
                self._decimal(snapshot.fatigue.evidence_coverage) if snapshot.fatigue else None
            ),
            data_completeness=self._decimal(snapshot.data_quality.confidence),
            snapshot_payload=payload,
            payload_hash=payload_hash,
        )
        self.db.add(record)
        try:
            self.db.commit()
            self.db.refresh(record)
        except IntegrityError as exc:
            self.db.rollback()
            if not self._is_snapshot_duplicate_error(exc):
                raise
            concurrent = self._find_duplicate(user_id, cutoff, payload_hash)
            if concurrent is None:
                raise
            return _SaveOutcome(record=concurrent, created=False, duplicate=True)
        return _SaveOutcome(record=record, created=True, duplicate=False)

    def list_snapshots(
        self,
        *,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> RunnerStateSnapshotListResponse:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise BadRequestError("start_date must be on or before end_date.")

        filters = [RunnerStateSnapshotRecord.user_id == user_id]
        if start_date is not None:
            filters.append(RunnerStateSnapshotRecord.data_cutoff_date >= start_date)
        if end_date is not None:
            filters.append(RunnerStateSnapshotRecord.data_cutoff_date <= end_date)

        total = int(
            self.db.scalar(
                select(func.count()).select_from(RunnerStateSnapshotRecord).where(*filters)
            )
            or 0
        )
        summary_columns = (
            RunnerStateSnapshotRecord.id,
            RunnerStateSnapshotRecord.snapshot_date,
            RunnerStateSnapshotRecord.data_cutoff_date,
            RunnerStateSnapshotRecord.calculated_at,
            RunnerStateSnapshotRecord.created_at,
            RunnerStateSnapshotRecord.trigger_type,
            RunnerStateSnapshotRecord.snapshot_schema_version,
            RunnerStateSnapshotRecord.ruleset_version,
            RunnerStateSnapshotRecord.distance_7d_km,
            RunnerStateSnapshotRecord.distance_28d_km,
            RunnerStateSnapshotRecord.volume_trend,
            RunnerStateSnapshotRecord.training_consistency,
            RunnerStateSnapshotRecord.fatigue_state,
            RunnerStateSnapshotRecord.training_phase,
            RunnerStateSnapshotRecord.risk_flag_count,
            RunnerStateSnapshotRecord.evidence_coverage,
            RunnerStateSnapshotRecord.data_completeness,
        )
        records = list(
            self.db.scalars(
                select(RunnerStateSnapshotRecord)
                .options(load_only(*summary_columns))
                .where(*filters)
                .order_by(
                    RunnerStateSnapshotRecord.data_cutoff_date.desc(),
                    RunnerStateSnapshotRecord.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        )
        return RunnerStateSnapshotListResponse(
            items=[self._to_list_item(record) for record in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_snapshot(self, *, user_id: int, snapshot_id: int) -> RunnerStateSnapshotDetail:
        record = self.db.scalar(
            select(RunnerStateSnapshotRecord).where(
                RunnerStateSnapshotRecord.id == snapshot_id,
                RunnerStateSnapshotRecord.user_id == user_id,
            )
        )
        if record is None:
            raise NotFoundError("Runner-state snapshot not found.")
        return self._to_detail(record)

    def _find_duplicate(
        self, user_id: int, data_cutoff_date: date, payload_hash: str
    ) -> RunnerStateSnapshotRecord | None:
        return self.db.scalar(
            select(RunnerStateSnapshotRecord).where(
                RunnerStateSnapshotRecord.user_id == user_id,
                RunnerStateSnapshotRecord.data_cutoff_date == data_cutoff_date,
                RunnerStateSnapshotRecord.payload_hash == payload_hash,
            )
        )

    @staticmethod
    def _is_snapshot_duplicate_error(exc: IntegrityError) -> bool:
        message = str(exc.orig).lower()
        constraint = "uq_runner_state_snapshot_user_cutoff_hash"
        sqlite_columns = (
            "runner_state_snapshots.user_id",
            "runner_state_snapshots.data_cutoff_date",
            "runner_state_snapshots.payload_hash",
        )
        return constraint in message or (
            "unique" in message and all(column in message for column in sqlite_columns)
        )

    @staticmethod
    def _ruleset_version(snapshot: RunnerStateSnapshot) -> str:
        if snapshot.inference_metadata is None or not snapshot.inference_metadata.ruleset_version:
            raise ValueError("Runner-state snapshot is missing ruleset_version.")
        return snapshot.inference_metadata.ruleset_version

    def _business_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("Snapshot clock must return a timezone-aware datetime.")
        return value.astimezone(APP_TIMEZONE)

    @staticmethod
    def _to_database_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(APP_TIMEZONE).replace(tzinfo=None)

    @staticmethod
    def _to_api_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=APP_TIMEZONE)
        return value.astimezone(APP_TIMEZONE)

    @staticmethod
    def _decimal(value: float | int | Decimal | None) -> Decimal | None:
        return Decimal(str(value)) if value is not None else None

    @staticmethod
    def _enum_value(value: object) -> str:
        enum_value = getattr(value, "value", value)
        return str(enum_value)

    def _to_list_item(self, record: RunnerStateSnapshotRecord) -> RunnerStateSnapshotListItem:
        return RunnerStateSnapshotListItem(
            id=record.id,
            snapshot_date=record.snapshot_date,
            data_cutoff_date=record.data_cutoff_date,
            calculated_at=self._to_api_datetime(record.calculated_at),
            created_at=self._to_api_datetime(record.created_at),
            trigger_type=record.trigger_type,
            snapshot_schema_version=record.snapshot_schema_version,
            ruleset_version=record.ruleset_version,
            distance_7d_km=float(record.distance_7d_km) if record.distance_7d_km is not None else None,
            distance_28d_km=float(record.distance_28d_km) if record.distance_28d_km is not None else None,
            volume_trend=record.volume_trend,
            training_consistency=record.training_consistency,
            fatigue_state=record.fatigue_state,
            training_phase=record.training_phase,
            risk_flag_count=record.risk_flag_count,
            evidence_coverage=(
                float(record.evidence_coverage) if record.evidence_coverage is not None else None
            ),
            data_completeness=(
                float(record.data_completeness) if record.data_completeness is not None else None
            ),
        )

    def _to_detail(self, record: RunnerStateSnapshotRecord) -> RunnerStateSnapshotDetail:
        return RunnerStateSnapshotDetail(
            **self._to_list_item(record).model_dump(),
            snapshot_payload=record.snapshot_payload,
        )
