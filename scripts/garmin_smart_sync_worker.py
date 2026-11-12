"""Run outside Web workers: python -m scripts.garmin_smart_sync_worker."""
import argparse
import logging
from datetime import datetime, timedelta
from threading import Event
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from planner_core.config import get_settings
from planner_core.database.models import ExternalAccountConnection, ExternalSyncJob, GarminSmartSyncState, UserAccount
from server.services import garmin_smart_sync_service as coordinator

logger = logging.getLogger(__name__)


def tick(session_factory, pipeline):
    now = datetime.utcnow()
    with session_factory() as db:
        # Lock each expired owner before fencing it; old workers cannot commit
        # after this transaction has revoked their token.
        expired = db.scalars(select(GarminSmartSyncState).where(
            GarminSmartSyncState.lease_token.is_not(None), GarminSmartSyncState.lease_until <= now)
            .with_for_update(skip_locked=True).limit(50)).all()
        for state in expired:
            db.execute(update(ExternalSyncJob).where(ExternalSyncJob.id == state.active_job_id,
                ExternalSyncJob.status == 'running').values(status='failed', error_code='WORKER_LEASE_EXPIRED', finished_at=now))
            state.lease_token = state.lease_until = state.active_job_id = None
            state.error_category = 'WORKER'
            state.next_retry_at = now + timedelta(minutes=5)
        db.commit()
        ids = list(db.scalars(select(ExternalAccountConnection.user_id).join(UserAccount,
            UserAccount.id == ExternalAccountConnection.user_id).where(
            ExternalAccountConnection.provider == 'garmin', ExternalAccountConnection.status == 'connected',
            ExternalAccountConnection.auto_sync_enabled.is_(True), UserAccount.status == 'active')
            .order_by(ExternalAccountConnection.id).limit(1000)))
    for uid in ids:
        coordinator.request_safely(session_factory, uid, trigger='scheduled')
    with session_factory() as db:
        jobs = list(db.scalars(select(ExternalSyncJob.id).where(ExternalSyncJob.status == 'queued')
            .order_by(ExternalSyncJob.id).limit(20)))
    for job_id in jobs:
        try:
            with session_factory() as db:
                pipeline.run_job(db, job_id)
        except Exception as exc:
            logger.warning('smart_sync_job_failed exception_type=%s', type(exc).__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if not get_settings().garmin_smart_sync_enabled:
        parser.error('GARMIN_SMART_SYNC_ENABLED must be enabled after migration')
    from planner_core.database.session import SessionLocal
    from server.integrations.activity_sync.pipeline import ActivitySyncPipeline
    stop = Event()
    try:
        while True:
            try:
                tick(SessionLocal, ActivitySyncPipeline())
            except Exception as exc:
                logger.warning('smart_sync_tick_failed exception_type=%s', type(exc).__name__)
            if args.once:
                break
            stop.wait(30)
    except KeyboardInterrupt:
        stop.set()


if __name__ == '__main__':
    main()
