from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from server.schemas.training_read import RecentTrainingRead, TrainingDataQualityRead
from server.services.runner_state_service import build_runner_state_snapshot


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def empty_snapshot(user_id: int = 101):
    return build_runner_state_snapshot(
        runner_id=user_id,
        cycle=None,
        log_rows=[],
        planned_workouts=[],
        generated_at=NOW,
        timezone_name="Asia/Shanghai",
        calculation_window_end=NOW.date(),
    )


class FakeDependencies:
    def __init__(self) -> None:
        self.snapshot = empty_snapshot()
        self.history_items: list[object] = []
        self.recent = RecentTrainingRead(
            as_of_date=NOW.date(),
            window_days=7,
            items=[],
            total_sessions=0,
            total_distance_km=None,
            completed_key_sessions=0,
            rest_days=0,
        )
        self.quality = TrainingDataQualityRead(
            as_of_date=NOW.date(),
            window_days=14,
            valid_workout_count=0,
            coverage={"distance": 0, "duration": 0, "rpe": 0, "heart_rate": 0},
            missing_fields=["distance", "duration", "rpe", "heart_rate"],
            source_mix={},
            freshness_days=None,
        )
        self.today = (NOW.date(), None, [])
        self.cycle = None
        self.rules: list[object] = []
        self.evaluation = None
        self.seen_user_ids: list[int] = []

    def current_runner_state(self, user_id: int):
        self.seen_user_ids.append(user_id)
        return self.snapshot

    def runner_state_history(self, user_id: int, limit: int):
        self.seen_user_ids.append(user_id)
        return SimpleNamespace(items=self.history_items[:limit])

    def recent_training(
        self,
        user_id: int,
        days: int,
        limit: int,
        *,
        as_of_date=None,
    ):
        del as_of_date
        self.seen_user_ids.append(user_id)
        return self.recent.model_copy(update={"window_days": days, "items": self.recent.items[:limit]})

    def training_data_quality(
        self,
        user_id: int,
        window_days: int,
        *,
        as_of_date=None,
    ):
        del as_of_date
        self.seen_user_ids.append(user_id)
        return self.quality.model_copy(update={"window_days": window_days})

    def today_workouts(self, user_id: int):
        self.seen_user_ids.append(user_id)
        return self.today

    def current_cycle(self, user_id: int):
        self.seen_user_ids.append(user_id)
        return self.cycle

    def training_rules(self, scope: str, limit: int):
        return self.rules[:limit], len(self.rules)

    def evaluate_today(self, user_id: int, target_date: date):
        self.seen_user_ids.append(user_id)
        return self.evaluation
