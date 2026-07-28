from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from server.services import (
    planned_workout_service,
    training_cycle_lifecycle_service,
    training_load_service,
    training_rule_loop_service,
    training_rule_service,
)
from server.services.runner_state_service import RunnerStateService
from server.services.runner_state_snapshot_service import RunnerStateSnapshotService
from server.services.weekly_review_stats_service import local_today


@dataclass(frozen=True)
class CoachAgentToolDependencies:
    """Per-request service container. It never owns or closes the injected Session."""

    db: Session
    runner_state_service: RunnerStateService
    snapshot_service: RunnerStateSnapshotService

    @classmethod
    def from_session(cls, db: Session) -> "CoachAgentToolDependencies":
        runner_state = RunnerStateService(db)
        return cls(
            db=db,
            runner_state_service=runner_state,
            snapshot_service=RunnerStateSnapshotService(db, runner_state_service=runner_state),
        )

    def current_runner_state(self, user_id: int):
        return self.runner_state_service.get_current_for_user_id(user_id)

    def runner_state_history(self, user_id: int, limit: int):
        return self.snapshot_service.list_snapshots(user_id=user_id, limit=limit, offset=0)

    def recent_training(
        self,
        user_id: int,
        days: int,
        limit: int,
        *,
        as_of_date: date | None = None,
    ):
        return training_load_service.get_recent_training_read(
            self.db,
            user_id=user_id,
            days=days,
            limit=limit,
            as_of_date=as_of_date,
        )

    def training_data_quality(
        self,
        user_id: int,
        window_days: int,
        *,
        as_of_date: date | None = None,
    ):
        return training_load_service.get_training_data_quality_read(
            self.db,
            user_id=user_id,
            window_days=window_days,
            as_of_date=as_of_date,
        )

    def today_workouts(self, user_id: int):
        today = local_today()
        cycle = training_cycle_lifecycle_service.get_active_cycle(self.db, user_id)
        workouts = (
            planned_workout_service.get_today_workouts(self.db, today, user_id)
            if cycle is not None
            else []
        )
        return today, cycle, workouts

    def current_cycle(self, user_id: int):
        return training_cycle_lifecycle_service.get_active_cycle_with_blocks(self.db, user_id)

    def training_rules(self, scope: str, limit: int):
        return training_rule_service.list_rules(
            self.db,
            is_admin=False,
            scope=scope,
            enabled=True,
            limit=limit,
            offset=0,
        )

    def evaluate_today(self, user_id: int, target_date: date):
        return training_rule_loop_service.evaluate_today_readonly(
            self.db, user_id, target_date
        )
