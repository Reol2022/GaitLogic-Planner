from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from planner_core.database.models import (
    ExternalAccountConnection,
    ExternalActivity,
    ExternalSyncJob,
    PlanAdjustmentDraft,
    PlannedWorkout,
    TrainingCycle,
    WeeklyReviewReport,
    WorkoutLog,
)
from planner_core.enums import PlanAdjustmentDraftStatus, TrainingCycleStatus, WeeklyReviewStatus, WorkoutStatusNormalized
from server.schemas.simplified_workflow import TaskItemRead
from server.services.weekly_review_stats_service import local_today


COMPLETED_STATUSES = {
    WorkoutStatusNormalized.completed_high,
    WorkoutStatusNormalized.completed_normal,
    WorkoutStatusNormalized.completed_adjusted,
}


def list_tasks(db: Session, user_id: int, limit: int = 20) -> list[TaskItemRead]:
    tasks = [
        task
        for task in [
            _subjective_data_missing_task(db, user_id),
            _activity_needs_review_task(db, user_id),
            _provider_reauth_task(db, user_id),
            _sync_failed_task(db, user_id),
            _weekly_review_ready_task(db, user_id),
            _plan_adjustment_ready_task(db, user_id),
            _cycle_ending_soon_task(db, user_id),
        ]
        if task is not None
    ]
    tasks.sort(key=lambda item: (item.priority, item.created_at or datetime.utcnow()))
    return tasks[: max(1, min(limit, 50))]


def _subjective_data_missing_task(db: Session, user_id: int) -> TaskItemRead | None:
    today = local_today()
    start = today - timedelta(days=21)
    stmt = (
        select(func.count(WorkoutLog.id), func.min(PlannedWorkout.id))
        .join(PlannedWorkout, PlannedWorkout.id == WorkoutLog.planned_workout_id)
        .where(
            WorkoutLog.user_id == user_id,
            WorkoutLog.subjective_status == "pending",
            PlannedWorkout.workout_date >= start,
            PlannedWorkout.workout_date <= today,
            WorkoutLog.status_normalized.in_(COMPLETED_STATUSES),
        )
    )
    count, source_id = db.execute(stmt).one()
    if not count:
        return None
    return TaskItemRead(
        task_key="subjective_data_missing",
        task_type="subjective_data_missing",
        title="补充训练感受",
        description=f"有 {count} 条已完成训练还缺少 RPE 或体感。",
        priority=40,
        count=count,
        action_path=f"/workouts/{source_id}/log" if source_id else "/today",
        source_type="planned_workout",
        source_id=source_id,
    )


def _activity_needs_review_task(db: Session, user_id: int) -> TaskItemRead | None:
    count, source_id = db.execute(
        select(func.count(ExternalActivity.id), func.min(ExternalActivity.id)).where(
            ExternalActivity.user_id == user_id,
            or_(
                ExternalActivity.processing_status == "needs_review",
                ExternalActivity.resolution_status == "needs_review",
            ),
        )
    ).one()
    if not count:
        return None
    return TaskItemRead(
        task_key="activity_needs_review",
        task_type="activity_needs_review",
        title="确认同步活动",
        description=f"有 {count} 条设备活动需要你确认归属。",
        priority=30,
        count=count,
        action_path="/data-sync/garmin",
        source_type="external_activity",
        source_id=source_id,
    )


def _provider_reauth_task(db: Session, user_id: int) -> TaskItemRead | None:
    connection = db.scalar(
        select(ExternalAccountConnection)
        .where(
            ExternalAccountConnection.user_id == user_id,
            ExternalAccountConnection.status == "reauthentication_required",
        )
        .order_by(ExternalAccountConnection.updated_at.desc())
    )
    if connection is None:
        return None
    return TaskItemRead(
        task_key=f"provider_reauthentication_required:{connection.provider}",
        task_type="provider_reauthentication_required",
        title="重新连接数据平台",
        description=f"{connection.provider} 需要重新认证后才能继续同步。",
        priority=20,
        action_path=f"/data-sync/{connection.provider}",
        source_type="external_account_connection",
        source_id=connection.id,
        created_at=connection.updated_at,
    )


def _sync_failed_task(db: Session, user_id: int) -> TaskItemRead | None:
    since = datetime.utcnow() - timedelta(days=7)
    count, source_id = db.execute(
        select(func.count(ExternalSyncJob.id), func.max(ExternalSyncJob.id)).where(
            ExternalSyncJob.user_id == user_id,
            ExternalSyncJob.status.in_(["failed", "partially_succeeded"]),
            ExternalSyncJob.created_at >= since,
        )
    ).one()
    if not count:
        return None
    return TaskItemRead(
        task_key="sync_failed",
        task_type="sync_failed",
        title="数据同步未完成",
        description=f"最近有 {count} 个同步任务失败或部分成功。",
        priority=25,
        count=count,
        action_path="/data-sync",
        source_type="external_sync_job",
        source_id=source_id,
    )


def _weekly_review_ready_task(db: Session, user_id: int) -> TaskItemRead | None:
    report = db.scalar(
        select(WeeklyReviewReport)
        .where(
            WeeklyReviewReport.user_id == user_id,
            WeeklyReviewReport.status == WeeklyReviewStatus.success,
            WeeklyReviewReport.generated_at >= datetime.utcnow() - timedelta(days=14),
        )
        .order_by(WeeklyReviewReport.generated_at.desc())
    )
    if report is None:
        return None
    return TaskItemRead(
        task_key=f"weekly_review_ready:{report.id}",
        task_type="weekly_review_ready",
        title="查看本周复盘",
        description="本周复盘已生成，可以确认感受和下周调整。",
        priority=50,
        action_path=f"/weekly-review?review_id={report.id}",
        source_type="weekly_review_report",
        source_id=report.id,
        created_at=report.generated_at,
    )


def _plan_adjustment_ready_task(db: Session, user_id: int) -> TaskItemRead | None:
    draft = db.scalar(
        select(PlanAdjustmentDraft)
        .where(
            PlanAdjustmentDraft.user_id == user_id,
            PlanAdjustmentDraft.status.in_(
                [
                    PlanAdjustmentDraftStatus.ready,
                    PlanAdjustmentDraftStatus.conflict,
                    PlanAdjustmentDraftStatus.draft,
                ]
            ),
        )
        .order_by(PlanAdjustmentDraft.updated_at.desc())
    )
    if draft is None:
        return None
    return TaskItemRead(
        task_key=f"plan_adjustment_ready:{draft.id}",
        task_type="plan_adjustment_ready",
        title="确认下周调整",
        description="有训练计划调整草稿等待确认。",
        priority=55,
        action_path="/weekly-review",
        source_type="plan_adjustment_draft",
        source_id=draft.id,
        created_at=draft.updated_at,
    )


def _cycle_ending_soon_task(db: Session, user_id: int) -> TaskItemRead | None:
    today = local_today()
    cycle = db.scalar(
        select(TrainingCycle).where(
            TrainingCycle.user_id == user_id,
            TrainingCycle.status == TrainingCycleStatus.active,
        )
    )
    if cycle is None:
        return None
    end_date = cycle.actual_end_date or cycle.end_date
    if end_date is None or end_date < today or (end_date - today).days > 14:
        return None
    return TaskItemRead(
        task_key=f"cycle_ending_soon:{cycle.id}",
        task_type="cycle_ending_soon",
        title="当前训练周期即将结束",
        description=f"当前周期将在 {end_date.isoformat()} 结束。",
        priority=70,
        action_path="/training-plan",
        source_type="training_cycle",
        source_id=cycle.id,
    )
