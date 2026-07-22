from __future__ import annotations

import logging
import sys
import time

from planner_core.config import get_settings
from planner_core.database.session import SessionLocal
from server.integrations.activity_sync.pipeline import ActivitySyncPipeline

logger = logging.getLogger(__name__)


def process_next_job() -> bool:
    with SessionLocal() as db:
        result = ActivitySyncPipeline().run_next_job(db)
        if result is None:
            return False
        outcome = result.sync_outcome
        snapshot_status = (
            result.runner_state_snapshot.status.value
            if result.runner_state_snapshot is not None
            else None
        )
        logger.info(
            "Processed external sync job id=%s sync_run_id=%s status=%s "
            "claimed=%s committed=%s runner_state_snapshot_status=%s",
            outcome.job_id,
            outcome.sync_run_id,
            outcome.final_status,
            outcome.claimed,
            outcome.committed,
            snapshot_status,
        )
        return True


def run_forever() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    logger.info("External sync worker started.")
    while True:
        try:
            process_next_job()
        except Exception:
            logger.exception("External sync worker loop failed; will retry after sleep.")
        time.sleep(max(settings.garmin_sync_worker_poll_seconds, 1))


if __name__ == "__main__":
    run_forever()
