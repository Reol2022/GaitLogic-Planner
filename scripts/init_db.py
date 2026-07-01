from __future__ import annotations

from pathlib import Path
import sys

import pymysql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.config import get_settings
from planner_core.database.base import Base
from planner_core.database.models import (  # noqa: F401
    AIPlanDraft,
    AIPlanDraftWorkout,
    AIPlanCoachPreference,
    AIPlanJob,
    AIPlanQuota,
    AdminAISettings,
    AdminSystemSettings,
    BlockReview,
    DailyRecoveryCheckin,
    ExcelImportJob,
    FeatureAccess,
    Feedback,
    PaceProfile,
    PaceRule,
    PaceZone,
    PlanImportAudit,
    PlanAdjustmentDraft,
    PlanAdjustmentItem,
    PlannedWorkout,
    TrainingBlock,
    TrainingCycle,
    TrainingReadinessAssessment,
    UsageEvent,
    UserAccount,
    WeeklyReviewReport,
    WorkoutLog,
)
from planner_core.database.session import engine


def create_database_if_missing() -> None:
    settings = get_settings()
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def main() -> None:
    create_database_if_missing()
    Base.metadata.create_all(bind=engine)
    print("Database gaitlogic_planner initialized successfully.")


if __name__ == "__main__":
    main()
