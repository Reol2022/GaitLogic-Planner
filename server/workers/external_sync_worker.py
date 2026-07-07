from __future__ import annotations

import logging
import sys
import time

from planner_core.config import get_settings
from planner_core.database.session import SessionLocal
from server.services.garmin_sync_service import run_next_sync_job

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
                job = run_next_sync_job(db)
                if job is not None:
                    logger.info("Processed external sync job id=%s status=%s", job.id, job.status)
        except Exception:
            logger.exception("External sync worker loop failed; will retry after sleep.")
        time.sleep(max(settings.garmin_sync_worker_poll_seconds, 1))


if __name__ == "__main__":
    run_forever()
