from __future__ import annotations

from planner_core.database.session import SessionLocal
from server.integrations.activity_sync.pipeline import ActivitySyncPipeline


def run_sync_job_in_background(job_id: int) -> None:
    with SessionLocal() as db:
        ActivitySyncPipeline().run_job(db, job_id)
