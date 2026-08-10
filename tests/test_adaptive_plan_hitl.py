from __future__ import annotations

from datetime import date
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from langgraph.types import Command
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from planner_core.adaptive_plan.schemas import PlanValue, ProposalCandidateChange, TargetPlanFact
from planner_core.config import get_settings
from planner_core.database.base import Base
from planner_core.database.models import (
    AdaptivePlanVersionRecord,
    PlannedWorkout,
    TrainingBlock,
    TrainingCycle,
    UserAccount,
)
from planner_core.enums import BlockType, PlanAdjustmentAction, WorkoutMainTypeNormalized
from planner_core.weekly_review.aggregation import build_weekly_facts
from planner_core.weekly_review.schemas import PlannedSessionFact, WeeklyPeriod, WorkoutSessionFact
from scripts.upgrade_v0130_adaptive_plan import downgrade, upgrade
from server.adaptive_workflow.checkpointer import SQLAlchemyCheckpointSaver
from server.adaptive_workflow.graph import build_adaptive_approval_graph
from server.common.exceptions import NotFoundError
from server.services.adaptive_plan_approval_service import AdaptivePlanApprovalService
from server.services.adaptive_plan_proposal_service import AdaptivePlanProposalService
from server.services.adaptive_plan_version_service import AdaptivePlanVersionService


@pytest.fixture(scope="module")
def mysql_factory():
    settings = get_settings()
    database = f"gaitlogic_test_adaptive_{uuid4().hex[:10]}"
    try:
        admin = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
    except pymysql.MySQLError as exc:
        pytest.skip(f"isolated MySQL is unavailable: {exc.__class__.__name__}")
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    except pymysql.MySQLError as exc:
        admin.close()
        pytest.skip(f"isolated MySQL database creation is unavailable: {exc.__class__.__name__}")
    admin.close()
    url = (
        f"mysql+pymysql://{quote_plus(settings.mysql_user)}:{quote_plus(settings.mysql_password)}@"
        f"{settings.mysql_host}:{settings.mysql_port}/{database}?charset=utf8mb4"
    )
    engine = create_engine(url, future=True, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()
        cleanup = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
        with cleanup.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cleanup.close()


def create_target(db: Session, marker: str):
    user = UserAccount(username=f"fictional-adaptive-{marker}", password_hash="fictional-hash")
    cycle = TrainingCycle(user=user, name="虚构周期", start_date=date(2026, 7, 1), end_date=date(2026, 8, 31))
    block = TrainingBlock(
        user=user,
        cycle=cycle,
        block_name="虚构目标周",
        block_type=BlockType.week,
        week_index=1,
        sort_order=1,
        start_date=date(2026, 7, 13),
        end_date=date(2026, 7, 19),
    )
    workout = PlannedWorkout(
        user=user,
        cycle=cycle,
        block=block,
        workout_date=date(2026, 7, 13),
        planned_content="虚构轻松跑 10km",
        planned_distance_km=10,
        main_type_raw="easy",
        main_type_normalized=WorkoutMainTypeNormalized.easy,
        sort_order=1,
    )
    db.add(workout)
    db.commit()
    return user, cycle, workout


def canonical_facts():
    start = date(2026, 7, 6)
    end = date(2026, 7, 12)
    return build_weekly_facts(
        period=WeeklyPeriod(week_start=start, week_end=end, timezone="Asia/Shanghai"),
        plans=[PlannedSessionFact(plan_id=1, session_date=start, main_type="easy", distance_km=8)],
        logs=[WorkoutSessionFact(log_id=1, planned_workout_id=1, activity_date=start, main_type="easy", distance_km=8, duration_minutes=45, status="completed_normal")],
        runner_state_samples=[],
        as_of_date=end,
    )


def persist_proposal(db: Session, user, cycle, workout):
    proposal = AdaptivePlanProposalService().create_proposal(
        user_id=user.id,
        weekly_facts=canonical_facts(),
        target_plans=[
            TargetPlanFact(
                plan_id=workout.id,
                user_id=user.id,
                workout_date=workout.workout_date,
                value=PlanValue(content=workout.planned_content, distance_km=10, main_type="easy"),
                plan_version=workout.plan_version,
            )
        ],
        candidates=[
            ProposalCandidateChange(
                plan_id=workout.id,
                action=PlanAdjustmentAction.reduce,
                after=PlanValue(content="虚构轻松跑 8km", distance_km=8, main_type="easy"),
                reason="虚构规则证据支持的减量。",
                rule_evidence=["NO_MATERIAL_WEEKLY_DEVIATION"],
            )
        ],
    )
    return AdaptivePlanApprovalService().persist_proposal(
        db, user_id=user.id, proposal=proposal, cycle_id=cycle.id
    )


def test_approve_applies_once_and_records_version(mysql_factory) -> None:
    with mysql_factory() as db:
        user, cycle, workout = create_target(db, uuid4().hex[:8])
        record = persist_proposal(db, user, cycle, workout)
        service = AdaptivePlanApprovalService()
        first = service.approve(db, user_id=user.id, proposal_id=record.id)
        second = service.approve(db, user_id=user.id, proposal_id=record.id)
        db.refresh(workout)
        assert first.duplicate is False
        assert second.duplicate is True
        assert workout.planned_distance_km == 8
        assert workout.plan_version == 2
        assert db.scalar(select(AdaptivePlanVersionRecord).where(AdaptivePlanVersionRecord.proposal_id == record.id)) is not None


def test_reject_never_changes_plan(mysql_factory) -> None:
    with mysql_factory() as db:
        user, cycle, workout = create_target(db, uuid4().hex[:8])
        record = persist_proposal(db, user, cycle, workout)
        result = AdaptivePlanApprovalService().reject(db, user_id=user.id, proposal_id=record.id)
        db.refresh(workout)
        assert result.status == "rejected"
        assert workout.planned_distance_km == 10
        assert db.scalar(select(AdaptivePlanVersionRecord).where(AdaptivePlanVersionRecord.proposal_id == record.id)) is None


def test_cross_user_approval_does_not_disclose_or_write(mysql_factory) -> None:
    with mysql_factory() as db:
        owner, cycle, workout = create_target(db, uuid4().hex[:8])
        record = persist_proposal(db, owner, cycle, workout)
        other = UserAccount(username=f"fictional-other-{uuid4().hex[:8]}", password_hash="fictional-hash")
        db.add(other)
        db.commit()
        with pytest.raises(NotFoundError):
            AdaptivePlanApprovalService().approve(db, user_id=other.id, proposal_id=record.id)
        db.refresh(workout)
        assert workout.plan_version == 1


def test_controlled_rollback_creates_new_audit_version(mysql_factory) -> None:
    with mysql_factory() as db:
        user, cycle, workout = create_target(db, uuid4().hex[:8])
        record = persist_proposal(db, user, cycle, workout)
        applied = AdaptivePlanApprovalService().approve(db, user_id=user.id, proposal_id=record.id)
        rollback = AdaptivePlanVersionService().rollback(
            db, user_id=user.id, version_id=applied.plan_version_id, reason="虚构验收回滚"
        )
        db.refresh(workout)
        assert workout.planned_distance_km == 10
        assert workout.plan_version == 3
        assert rollback.rollback_of_version_id == applied.plan_version_id


def test_langgraph_interrupt_resumes_from_sqlalchemy_checkpoint(mysql_factory) -> None:
    saver = SQLAlchemyCheckpointSaver(mysql_factory)
    graph = build_adaptive_approval_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": f"adaptive-{uuid4()}"}}
    paused = graph.invoke({"user_id": 7, "proposal_id": 99, "decision": None}, config)
    assert "__interrupt__" in paused
    resumed = graph.invoke(Command(resume="approve"), config)
    assert resumed["decision"] == "approve"


def test_migration_upgrade_and_downgrade_are_reversible(mysql_factory) -> None:
    engine = mysql_factory.kw["bind"]
    with engine.begin() as connection:
        downgrade(connection)
        assert "adaptive_plan_versions" not in inspect(connection).get_table_names()
        upgrade(connection)
        assert {
            "adaptive_plan_versions",
            "adaptive_workflow_checkpoints",
            "adaptive_workflow_checkpoint_writes",
        }.issubset(set(inspect(connection).get_table_names()))
