from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner_core.database.models import (
    DailyRecoveryCheckin,
    ExternalAccountConnection,
    ExternalActivity,
    ExternalSyncJob,
    TrainingBlock,
)
from server.schemas.simplified_workflow import (
    DataSyncProviderSummary,
    DataSyncSummaryRead,
    RecoveryQuickRead,
    TodayDashboardRead,
    TrainingPlanOverviewRead,
)
from server.services import planned_workout_service, task_center_service
from server.services.training_cycle_lifecycle_service import get_active_cycle
from server.services.weekly_review_stats_service import local_today


def get_data_sync_summary(db: Session, user_id: int) -> DataSyncSummaryRead:
    connections = db.scalars(
        select(ExternalAccountConnection)
        .where(ExternalAccountConnection.user_id == user_id)
        .order_by(ExternalAccountConnection.provider, ExternalAccountConnection.created_at.desc())
    ).all()
    providers = [
        DataSyncProviderSummary(
            provider=connection.provider,
            connected=connection.status == "connected",
            status=connection.status,
            masked_account_identifier=connection.masked_account_identifier,
            auto_import_enabled=connection.auto_import_enabled,
            auto_sync_enabled=connection.auto_sync_enabled,
            auto_sync_last_run_at=connection.auto_sync_last_run_at,
            last_successful_sync_at=connection.last_successful_sync_at,
            last_error_code=connection.last_error_code,
        )
        for connection in connections
    ]
    needs_review_count = db.scalar(
        select(func.count(ExternalActivity.id)).where(
            ExternalActivity.user_id == user_id,
            ExternalActivity.resolution_status == "needs_review",
        )
    ) or 0
    failed_job_count = db.scalar(
        select(func.count(ExternalSyncJob.id)).where(
            ExternalSyncJob.user_id == user_id,
            ExternalSyncJob.status.in_(["failed", "partially_succeeded"]),
            ExternalSyncJob.created_at >= datetime.utcnow() - timedelta(days=7),
        )
    ) or 0
    return DataSyncSummaryRead(
        providers=providers,
        connected_count=sum(1 for item in providers if item.connected),
        needs_review_count=needs_review_count,
        failed_job_count=failed_job_count,
    )


def get_today_dashboard(db: Session, user_id: int) -> TodayDashboardRead:
    today = local_today()
    active_cycle = get_active_cycle(db, user_id)
    checkin = db.scalar(
        select(DailyRecoveryCheckin).where(
            DailyRecoveryCheckin.user_id == user_id,
            DailyRecoveryCheckin.checkin_date == today,
        )
    )
    return TodayDashboardRead(
        today=today,
        has_active_cycle=active_cycle is not None,
        workouts=planned_workout_service.get_today_workouts(db, today, user_id) if active_cycle else [],
        tasks=task_center_service.list_tasks(db, user_id, limit=3),
        data_sync=get_data_sync_summary(db, user_id),
        recovery_checkin_completed=checkin is not None,
    )


def get_training_plan_overview(db: Session, user_id: int) -> TrainingPlanOverviewRead:
    today = local_today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    active_cycle = get_active_cycle(db, user_id)
    week_workouts = planned_workout_service.list_planned_workouts(
        db,
        user_id,
        cycle_id=active_cycle.id if active_cycle else None,
        start_date=week_start,
        end_date=week_end,
    ) if active_cycle else []
    block = None
    if active_cycle:
        block_model = db.scalar(
            select(TrainingBlock)
            .where(
                TrainingBlock.user_id == user_id,
                TrainingBlock.cycle_id == active_cycle.id,
                TrainingBlock.start_date <= today,
                TrainingBlock.end_date >= today,
            )
            .order_by(TrainingBlock.start_date.desc())
        )
        if block_model:
            block = {
                "id": block_model.id,
                "name": block_model.block_name,
                "start_date": block_model.start_date,
                "end_date": block_model.end_date,
                "focus": block_model.focus,
            }
    return TrainingPlanOverviewRead(
        has_active_cycle=active_cycle is not None,
        active_cycle=active_cycle,
        current_block=block,
        week_start=week_start,
        week_end=week_end,
        week_workouts=week_workouts,
        primary_actions=[
            {"label": "查看当前计划", "path": "/workouts"},
            {"label": "AI 制定新计划", "path": "/ai-plan"},
            {"label": "导入外部课表", "path": "/plan-imports"},
            {"label": "查看历史计划", "path": "/cycles"},
        ],
        advanced_links=[
            {"label": "训练周期", "path": "/cycles"},
            {"label": "训练块", "path": "/blocks"},
            {"label": "配速规则", "path": "/pace-rules"},
            {"label": "配速计算器", "path": "/pace-calculator"},
        ],
    )


def recovery_quick_from_checkin(checkin: DailyRecoveryCheckin | None) -> RecoveryQuickRead:
    if checkin is None:
        return RecoveryQuickRead(checkin_date=local_today(), raw=None)
    return RecoveryQuickRead(
        checkin_date=checkin.checkin_date,
        leg_feeling=_reverse_leg_feeling(checkin.leg_feeling),
        fatigue=_reverse_fatigue(checkin.subjective_fatigue),
        pain=_reverse_pain(checkin.pain_level),
        raw={
            "leg_feeling": checkin.leg_feeling,
            "subjective_fatigue": checkin.subjective_fatigue,
            "pain_level": checkin.pain_level,
        },
    )


def _reverse_leg_feeling(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 4:
        return "good"
    if value <= 2:
        return "bad"
    return "normal"


def _reverse_fatigue(value: int | None) -> str | None:
    if value is None:
        return None
    if value <= 2:
        return "low"
    if value >= 4:
        return "high"
    return "normal"


def _reverse_pain(value: int | None) -> str | None:
    if value is None or value <= 0:
        return "none"
    if value <= 3:
        return "mild"
    return "obvious"
