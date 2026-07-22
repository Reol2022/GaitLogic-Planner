from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from planner_core.database.models import (
    ExternalSyncJob,
    RunnerStateSnapshotTriggerReceipt,
    UserAccount,
)
from planner_core.enums import (
    RunnerStateAutoSnapshotStatus,
    RunnerStateSnapshotReceiptStatus,
    RunnerStateSnapshotTriggerType,
)
from server.schemas.runner_state_auto_snapshot import RunnerStateAutoSnapshotResult
from server.services.runner_state_snapshot_serializer import serialize_runner_state_snapshot
from server.services.runner_state_snapshot_service import RunnerStateSnapshotService
from server.services.weekly_review_stats_service import APP_TIMEZONE

logger = logging.getLogger(__name__)

GARMIN_SYNC_TRIGGER_PREFIX = "garmin-sync:"
RUNNER_STATE_RECEIPT_LEASE = timedelta(minutes=15)

_TERMINAL_STATUSES = {
    RunnerStateSnapshotReceiptStatus.CREATED,
    RunnerStateSnapshotReceiptStatus.DUPLICATE_PAYLOAD,
}
_REOPENABLE_STATUSES = {
    RunnerStateSnapshotReceiptStatus.SKIPPED_NO_MATERIAL_CHANGE,
    RunnerStateSnapshotReceiptStatus.SKIPPED_NOT_COMMITTED,
    RunnerStateSnapshotReceiptStatus.FAILED_NON_BLOCKING,
}


def build_garmin_sync_trigger_reference(sync_run_id: str) -> str:
    if not isinstance(sync_run_id, str) or not sync_run_id or sync_run_id != sync_run_id.strip():
        raise ValueError("sync_run_id must be a non-empty canonical UUID string")
    try:
        parsed = UUID(sync_run_id)
    except (ValueError, AttributeError) as exc:
        raise ValueError("sync_run_id must be a canonical UUID string") from exc
    if str(parsed) != sync_run_id:
        raise ValueError("sync_run_id must use canonical lowercase UUID form")
    trigger_reference = f"{GARMIN_SYNC_TRIGGER_PREFIX}{sync_run_id}"
    if len(trigger_reference) > 128:
        raise ValueError("Garmin sync trigger reference exceeds 128 characters")
    return trigger_reference


@dataclass(frozen=True)
class _ReceiptClaim:
    receipt_id: int
    processing_token: str | None
    result_status: RunnerStateAutoSnapshotStatus | None = None
    snapshot_id: int | None = None

    @property
    def acquired(self) -> bool:
        return self.processing_token is not None and self.result_status is None


class RunnerStateAutoSnapshotService:
    def __init__(
        self,
        db: Session,
        *,
        snapshot_service: RunnerStateSnapshotService | None = None,
        clock: Callable[[], datetime] | None = None,
        lease_duration: timedelta = RUNNER_STATE_RECEIPT_LEASE,
    ) -> None:
        if lease_duration.total_seconds() <= 0:
            raise ValueError("Receipt lease duration must be positive")
        self.db = db
        self.clock = clock or (lambda: datetime.now(APP_TIMEZONE))
        self.lease_duration = lease_duration
        self.snapshot_service = snapshot_service or RunnerStateSnapshotService(db, clock=self.clock)

    def process_garmin_sync_outcome(
        self,
        *,
        user_id: int,
        sync_job_id: int,
        sync_run_id: str,
        committed: bool,
        material_change_count: int,
    ) -> RunnerStateAutoSnapshotResult:
        if material_change_count < 0:
            raise ValueError("material_change_count must be non-negative")
        trigger_reference = build_garmin_sync_trigger_reference(sync_run_id)

        try:
            self._validate_sync_job_reference(
                user_id=user_id,
                sync_job_id=sync_job_id,
                sync_run_id=sync_run_id,
            )
            claim = self._claim_or_create_receipt(
                user_id=user_id,
                sync_job_id=sync_job_id,
                trigger_reference=trigger_reference,
                committed=committed,
                material_change_count=material_change_count,
            )
        except Exception as exc:
            self.db.rollback()
            logger.warning(
                "Runner-state auto snapshot receipt claim failed user_id=%s sync_job_id=%s "
                "sync_run_id=%s error_code=%s exception_type=%s",
                user_id,
                sync_job_id,
                sync_run_id,
                "AUTO_SNAPSHOT_TRANSACTION_FAILED",
                type(exc).__name__,
            )
            return RunnerStateAutoSnapshotResult(
                status=RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING,
                receipt_id=None,
                snapshot_id=None,
                trigger_reference=trigger_reference,
                error_code="AUTO_SNAPSHOT_TRANSACTION_FAILED",
            )

        if not claim.acquired:
            return RunnerStateAutoSnapshotResult(
                status=claim.result_status or RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING,
                receipt_id=claim.receipt_id,
                snapshot_id=claim.snapshot_id,
                trigger_reference=trigger_reference,
            )

        token = claim.processing_token
        assert token is not None
        if not committed:
            return self._complete_skip(
                claim=claim,
                trigger_reference=trigger_reference,
                status=RunnerStateSnapshotReceiptStatus.SKIPPED_NOT_COMMITTED,
            )
        if material_change_count == 0:
            return self._complete_skip(
                claim=claim,
                trigger_reference=trigger_reference,
                status=RunnerStateSnapshotReceiptStatus.SKIPPED_NO_MATERIAL_CHANGE,
            )
        return self._create_snapshot(
            user_id=user_id,
            sync_run_id=sync_run_id,
            sync_job_id=sync_job_id,
            trigger_reference=trigger_reference,
            claim=claim,
        )

    def _validate_sync_job_reference(
        self, *, user_id: int, sync_job_id: int, sync_run_id: str
    ) -> None:
        job_id = self.db.scalar(
            select(ExternalSyncJob.id).where(
                ExternalSyncJob.id == sync_job_id,
                ExternalSyncJob.user_id == user_id,
                ExternalSyncJob.sync_run_id == sync_run_id,
            )
        )
        if job_id is None:
            raise ValueError("sync job does not match the supplied user and sync run")

    def _claim_or_create_receipt(
        self,
        *,
        user_id: int,
        sync_job_id: int,
        trigger_reference: str,
        committed: bool,
        material_change_count: int,
    ) -> _ReceiptClaim:
        now = self._database_now()
        token = str(uuid4())
        receipt = RunnerStateSnapshotTriggerReceipt(
            user_id=user_id,
            trigger_type=RunnerStateSnapshotTriggerType.GARMIN_SYNC,
            trigger_reference=trigger_reference,
            status=RunnerStateSnapshotReceiptStatus.PROCESSING,
            snapshot_id=None,
            sync_job_id=sync_job_id,
            material_change_count=material_change_count,
            is_committed=committed,
            attempt_count=1,
            processing_token=token,
            locked_at=now,
            completed_at=None,
            error_code=None,
            safe_error_message=None,
        )
        try:
            with self.db.begin_nested():
                self.db.add(receipt)
                self.db.flush()
            self.db.commit()
            logger.info(
                "Runner-state snapshot receipt claimed receipt_id=%s user_id=%s sync_job_id=%s status=%s",
                receipt.id,
                user_id,
                sync_job_id,
                RunnerStateSnapshotReceiptStatus.PROCESSING.value,
            )
            return _ReceiptClaim(receipt_id=int(receipt.id), processing_token=token)
        except IntegrityError as exc:
            self.db.rollback()
            if not self._is_receipt_trigger_duplicate_error(exc):
                raise
        existing = self.db.scalar(
            select(RunnerStateSnapshotTriggerReceipt).where(
                RunnerStateSnapshotTriggerReceipt.user_id == user_id,
                RunnerStateSnapshotTriggerReceipt.trigger_type
                == RunnerStateSnapshotTriggerType.GARMIN_SYNC,
                RunnerStateSnapshotTriggerReceipt.trigger_reference == trigger_reference,
            )
        )
        if existing is None:
            raise RuntimeError("Concurrent receipt was not visible after unique conflict")
        return self._claim_existing(
            existing=existing,
            sync_job_id=sync_job_id,
            committed=committed,
            material_change_count=material_change_count,
            now=now,
        )

    def _claim_existing(
        self,
        *,
        existing: RunnerStateSnapshotTriggerReceipt,
        sync_job_id: int,
        committed: bool,
        material_change_count: int,
        now: datetime,
    ) -> _ReceiptClaim:
        if existing.status in _TERMINAL_STATUSES:
            self.db.rollback()
            return _ReceiptClaim(
                receipt_id=int(existing.id),
                processing_token=None,
                result_status=RunnerStateAutoSnapshotStatus.ALREADY_PROCESSED_TRIGGER,
                snapshot_id=int(existing.snapshot_id) if existing.snapshot_id is not None else None,
            )

        token = str(uuid4())
        base_conditions = [RunnerStateSnapshotTriggerReceipt.id == existing.id]
        if existing.status == RunnerStateSnapshotReceiptStatus.PROCESSING:
            expired_before = now - self.lease_duration
            if existing.locked_at is None or existing.locked_at >= expired_before:
                self.db.rollback()
                return _ReceiptClaim(
                    receipt_id=int(existing.id),
                    processing_token=None,
                    result_status=RunnerStateAutoSnapshotStatus.PROCESSING_BY_ANOTHER_WORKER,
                    snapshot_id=None,
                )
            base_conditions.extend(
                (
                    RunnerStateSnapshotTriggerReceipt.status
                    == RunnerStateSnapshotReceiptStatus.PROCESSING,
                    RunnerStateSnapshotTriggerReceipt.locked_at == existing.locked_at,
                    RunnerStateSnapshotTriggerReceipt.locked_at < expired_before,
                )
            )
        elif existing.status in _REOPENABLE_STATUSES:
            base_conditions.append(RunnerStateSnapshotTriggerReceipt.status == existing.status)
        else:
            self.db.rollback()
            return _ReceiptClaim(
                receipt_id=int(existing.id),
                processing_token=None,
                result_status=RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING,
                snapshot_id=None,
            )

        result = self.db.execute(
            update(RunnerStateSnapshotTriggerReceipt)
            .where(*base_conditions)
            .values(
                status=RunnerStateSnapshotReceiptStatus.PROCESSING,
                snapshot_id=None,
                sync_job_id=sync_job_id,
                material_change_count=material_change_count,
                is_committed=committed,
                attempt_count=RunnerStateSnapshotTriggerReceipt.attempt_count + 1,
                processing_token=token,
                locked_at=now,
                completed_at=None,
                error_code=None,
                safe_error_message=None,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            self.db.commit()
            logger.info(
                "Runner-state snapshot receipt reclaimed receipt_id=%s sync_job_id=%s",
                existing.id,
                sync_job_id,
            )
            return _ReceiptClaim(receipt_id=int(existing.id), processing_token=token)
        self.db.rollback()
        return _ReceiptClaim(
            receipt_id=int(existing.id),
            processing_token=None,
            result_status=RunnerStateAutoSnapshotStatus.PROCESSING_BY_ANOTHER_WORKER,
            snapshot_id=None,
        )

    def _complete_skip(
        self,
        *,
        claim: _ReceiptClaim,
        trigger_reference: str,
        status: RunnerStateSnapshotReceiptStatus,
    ) -> RunnerStateAutoSnapshotResult:
        token = claim.processing_token
        assert token is not None
        try:
            updated = self._complete_receipt_if_owned(
                receipt_id=claim.receipt_id,
                processing_token=token,
                status=status,
                snapshot_id=None,
            )
            if not updated:
                self.db.rollback()
                return self._lost_lease_result(claim.receipt_id, trigger_reference)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            return self._record_failure(
                claim=claim,
                trigger_reference=trigger_reference,
                error_code="AUTO_SNAPSHOT_TRANSACTION_FAILED",
                exception=exc,
            )
        return RunnerStateAutoSnapshotResult(
            status=RunnerStateAutoSnapshotStatus(status.value),
            receipt_id=claim.receipt_id,
            snapshot_id=None,
            trigger_reference=trigger_reference,
        )

    def _create_snapshot(
        self,
        *,
        user_id: int,
        sync_run_id: str,
        sync_job_id: int,
        trigger_reference: str,
        claim: _ReceiptClaim,
    ) -> RunnerStateAutoSnapshotResult:
        token = claim.processing_token
        assert token is not None
        stage = "RUNNER_STATE_CALCULATION_FAILED"
        try:
            owned = self.db.scalar(
                select(RunnerStateSnapshotTriggerReceipt.id).where(
                    RunnerStateSnapshotTriggerReceipt.id == claim.receipt_id,
                    RunnerStateSnapshotTriggerReceipt.status
                    == RunnerStateSnapshotReceiptStatus.PROCESSING,
                    RunnerStateSnapshotTriggerReceipt.processing_token == token,
                )
            )
            if owned is None:
                self.db.rollback()
                return self._lost_lease_result(claim.receipt_id, trigger_reference)
            user = self.db.get(UserAccount, user_id)
            if user is None:
                raise RuntimeError("Runner-state snapshot user no longer exists")
            snapshot = self.snapshot_service.runner_state_service.get_current(user)
            stage = "SNAPSHOT_SERIALIZATION_FAILED"
            serialize_runner_state_snapshot(snapshot)
            stage = "SNAPSHOT_PERSIST_FAILED"
            snapshot_result = self.snapshot_service.create_or_get_snapshot_in_transaction(
                user_id=user_id,
                snapshot=snapshot,
                trigger_type=RunnerStateSnapshotTriggerType.GARMIN_SYNC,
                trigger_reference=trigger_reference,
            )
            final_status = (
                RunnerStateSnapshotReceiptStatus.CREATED
                if snapshot_result.created
                else RunnerStateSnapshotReceiptStatus.DUPLICATE_PAYLOAD
            )
            stage = "RECEIPT_COMPLETION_FAILED"
            updated = self._complete_receipt_if_owned(
                receipt_id=claim.receipt_id,
                processing_token=token,
                status=final_status,
                snapshot_id=int(snapshot_result.snapshot.id),
            )
            if not updated:
                self.db.rollback()
                return self._lost_lease_result(claim.receipt_id, trigger_reference)
            stage = "AUTO_SNAPSHOT_TRANSACTION_FAILED"
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            return self._record_failure(
                claim=claim,
                trigger_reference=trigger_reference,
                error_code=stage,
                exception=exc,
            )

        result_status = RunnerStateAutoSnapshotStatus(final_status.value)
        logger.info(
            "Runner-state auto snapshot completed receipt_id=%s user_id=%s sync_job_id=%s "
            "sync_run_id=%s status=%s snapshot_id=%s",
            claim.receipt_id,
            user_id,
            sync_job_id,
            sync_run_id,
            result_status.value,
            snapshot_result.snapshot.id,
        )
        return RunnerStateAutoSnapshotResult(
            status=result_status,
            receipt_id=claim.receipt_id,
            snapshot_id=int(snapshot_result.snapshot.id),
            trigger_reference=trigger_reference,
        )

    def _complete_receipt_if_owned(
        self,
        *,
        receipt_id: int,
        processing_token: str,
        status: RunnerStateSnapshotReceiptStatus,
        snapshot_id: int | None,
    ) -> bool:
        result = self.db.execute(
            update(RunnerStateSnapshotTriggerReceipt)
            .where(
                RunnerStateSnapshotTriggerReceipt.id == receipt_id,
                RunnerStateSnapshotTriggerReceipt.status
                == RunnerStateSnapshotReceiptStatus.PROCESSING,
                RunnerStateSnapshotTriggerReceipt.processing_token == processing_token,
            )
            .values(
                status=status,
                snapshot_id=snapshot_id,
                processing_token=None,
                completed_at=self._database_now(),
                error_code=None,
                safe_error_message=None,
            )
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def _record_failure(
        self,
        *,
        claim: _ReceiptClaim,
        trigger_reference: str,
        error_code: str,
        exception: Exception,
    ) -> RunnerStateAutoSnapshotResult:
        token = claim.processing_token
        assert token is not None
        persisted = False
        try:
            result = self.db.execute(
                update(RunnerStateSnapshotTriggerReceipt)
                .where(
                    RunnerStateSnapshotTriggerReceipt.id == claim.receipt_id,
                    RunnerStateSnapshotTriggerReceipt.status
                    == RunnerStateSnapshotReceiptStatus.PROCESSING,
                    RunnerStateSnapshotTriggerReceipt.processing_token == token,
                )
                .values(
                    status=RunnerStateSnapshotReceiptStatus.FAILED_NON_BLOCKING,
                    snapshot_id=None,
                    processing_token=None,
                    completed_at=self._database_now(),
                    error_code=error_code,
                    safe_error_message="Automatic runner-state snapshot processing failed.",
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                self.db.commit()
                persisted = True
            else:
                self.db.rollback()
        except Exception as receipt_exc:
            self.db.rollback()
            logger.error(
                "Runner-state auto snapshot failure receipt could not be persisted receipt_id=%s "
                "error_code=%s exception_type=%s",
                claim.receipt_id,
                error_code,
                type(receipt_exc).__name__,
            )
        logger.warning(
            "Runner-state auto snapshot failed non-blocking receipt_id=%s error_code=%s "
            "exception_type=%s receipt_persisted=%s",
            claim.receipt_id,
            error_code,
            type(exception).__name__,
            persisted,
        )
        return RunnerStateAutoSnapshotResult(
            status=RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING,
            receipt_id=claim.receipt_id,
            snapshot_id=None,
            trigger_reference=trigger_reference,
            error_code=error_code,
        )

    def _lost_lease_result(
        self, receipt_id: int, trigger_reference: str
    ) -> RunnerStateAutoSnapshotResult:
        current = self.db.get(RunnerStateSnapshotTriggerReceipt, receipt_id)
        snapshot_id = int(current.snapshot_id) if current and current.snapshot_id is not None else None
        logger.warning(
            "Runner-state auto snapshot lost processing lease receipt_id=%s error_code=%s",
            receipt_id,
            "RECEIPT_PROCESSING_LEASE_LOST",
        )
        return RunnerStateAutoSnapshotResult(
            status=RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING,
            receipt_id=receipt_id,
            snapshot_id=snapshot_id,
            trigger_reference=trigger_reference,
            error_code="RECEIPT_PROCESSING_LEASE_LOST",
        )

    def _database_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("Automatic snapshot clock must return a timezone-aware datetime")
        return value.astimezone(APP_TIMEZONE).replace(tzinfo=None, microsecond=0)

    @staticmethod
    def _is_receipt_trigger_duplicate_error(exc: IntegrityError) -> bool:
        message = str(exc.orig).lower()
        constraint = "uq_runner_state_receipt_user_trigger_reference"
        sqlite_columns = (
            "runner_state_snapshot_trigger_receipt.user_id",
            "runner_state_snapshot_trigger_receipt.trigger_type",
            "runner_state_snapshot_trigger_receipt.trigger_reference",
        )
        return constraint in message or (
            "unique" in message and all(column in message for column in sqlite_columns)
        )
