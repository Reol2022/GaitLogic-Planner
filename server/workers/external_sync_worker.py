from __future__ import annotations

import logging
import sys
import time

from planner_core.config import get_settings
from planner_core.database.session import SessionLocal
from server.integrations.activity_sync.pipeline import ActivitySyncPipeline

logger = logging.getLogger(__name__)


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
            with SessionLocal() as db:
                outcome = ActivitySyncPipeline().run_next_job(db)
                if outcome is not None:
                    logger.info(
                        "Processed external sync job id=%s sync_run_id=%s status=%s claimed=%s committed=%s",
                        outcome.job_id,
                        outcome.sync_run_id,
                        outcome.final_status,
                        outcome.claimed,
                        outcome.committed,
                    )
        except Exception:
            logger.exception("External sync worker loop failed; will retry after sleep.")
        time.sleep(max(settings.garmin_sync_worker_poll_seconds, 1))


if __name__ == "__main__":
    run_forever()
