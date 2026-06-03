from __future__ import annotations

from datetime import date
import os
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.base import Base
from planner_core.database.models import (
    BlockReview,
    PaceRule,
    PlannedWorkout,
    TrainingBlock,
    TrainingCycle,
    WorkoutLog,
)
from planner_core.enums import (
    BlockType,
    ExcelImportStatus,
    WorkoutMainTypeNormalized,
    WorkoutStatusNormalized,
)


def test_enum_values_are_correct() -> None:
    assert [item.value for item in WorkoutStatusNormalized] == [
        "not_started",
        "completed_high",
        "completed_normal",
        "completed_adjusted",
        "missed",
        "rest",
        "rest_or_cancelled",
        "skipped",
        "unknown",
    ]
    assert [item.value for item in WorkoutMainTypeNormalized] == [
        "easy",
        "easy_with_speed",
        "interval_speed",
        "tempo",
        "recovery",
        "long_run",
        "rest",
        "mixed",
        "unknown",
    ]
    assert [item.value for item in BlockType] == ["week", "transition", "special"]
    assert [item.value for item in ExcelImportStatus] == [
        "pending",
        "running",
        "success",
        "partial_success",
        "failed",
    ]


@pytest.fixture(scope="module")
def mysql_session_factory():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = f"gaitlogic_planner_test_{uuid4().hex[:12]}"

    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=3,
        )
    except pymysql.MySQLError as exc:
        pytest.skip(f"MySQL is not available for integration tests: {exc}")

    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    connection.close()

    url = (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@"
        f"{host}:{port}/{database}?charset=utf8mb4"
    )
    engine = create_engine(url, pool_pre_ping=True, future=True)
    try:
        Base.metadata.create_all(bind=engine)
        yield sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    except OperationalError as exc:
        pytest.skip(f"MySQL schema tests could not start: {exc}")
    finally:
        engine.dispose()
        cleanup = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",
            autocommit=True,
        )
        with cleanup.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cleanup.close()


def create_plan_graph() -> tuple[TrainingCycle, TrainingBlock, PlannedWorkout]:
    cycle = TrainingCycle(
        name="2026夏训",
        goal="眉山东坡半马 1:11:30",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
    )
    block = TrainingBlock(
        cycle=cycle,
        block_name="Week 1：重新启动周",
        block_type=BlockType.week,
        week_index=1,
        sort_order=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 7),
    )
    planned = PlannedWorkout(
        cycle=cycle,
        block=block,
        workout_date=date(2026, 6, 2),
        date_text="2026-06-02",
        weekday="周二",
        month_text="6月",
        planned_content="轻松跑 10km",
        planned_distance_km=10,
        main_type_raw="E",
        main_type_normalized=WorkoutMainTypeNormalized.easy,
        source_sheet="计划索引",
        source_row=2,
        sort_order=1,
        workout_log=WorkoutLog(status_normalized=WorkoutStatusNormalized.not_started),
    )
    return cycle, block, planned


def test_can_create_all_tables(mysql_session_factory) -> None:
    inspector = inspect(mysql_session_factory.kw["bind"])
    assert {
        "training_cycles",
        "training_blocks",
        "planned_workouts",
        "workout_logs",
        "block_reviews",
        "pace_rules",
        "excel_import_jobs",
    }.issubset(set(inspector.get_table_names()))


def test_can_insert_cycle_block_workout_log_review_and_pace_rule(
    mysql_session_factory,
) -> None:
    session = mysql_session_factory()
    try:
        cycle, block, planned = create_plan_graph()
        block.block_review = BlockReview(
            planned_distance_km=50,
            actual_distance_km=48,
            completion_rate=96,
            review_text="重新启动顺利。",
        )
        pace_rule = PaceRule(
            code="E",
            name="轻松跑",
            target_pace_text="可对话强度",
            physiological_purpose="发展有氧基础。",
            sort_order=1,
        )
        session.add_all([planned, pace_rule])
        session.commit()

        saved = session.scalar(select(PlannedWorkout).where(PlannedWorkout.id == planned.id))
        assert saved is not None
        assert saved.block.block_review is not None
        assert saved.workout_log is not None
        assert saved.workout_log.status_normalized == WorkoutStatusNormalized.not_started
    finally:
        session.close()


def test_planned_workout_and_workout_log_are_one_to_one(mysql_session_factory) -> None:
    session = mysql_session_factory()
    try:
        _, _, planned = create_plan_graph()
        planned.workout_log = None
        session.add(planned)
        session.flush()
        session.add_all(
            [
                WorkoutLog(planned_workout_id=planned.id),
                WorkoutLog(planned_workout_id=planned.id),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()


def test_training_block_and_block_review_are_one_to_one(mysql_session_factory) -> None:
    session = mysql_session_factory()
    try:
        cycle, block, _ = create_plan_graph()
        session.add(cycle)
        session.flush()
        session.add_all(
            [
                BlockReview(block_id=block.id),
                BlockReview(block_id=block.id),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()


def test_deleting_training_cycle_cascades_children(mysql_session_factory) -> None:
    session = mysql_session_factory()
    try:
        cycle, block, planned = create_plan_graph()
        block.block_review = BlockReview(planned_distance_km=50)
        session.add(planned)
        session.commit()
        cycle_id = cycle.id
        block_id = block.id
        planned_id = planned.id
        log_id = planned.workout_log.id
        review_id = block.block_review.id

        session.delete(cycle)
        session.commit()

        assert session.scalar(select(TrainingCycle).where(TrainingCycle.id == cycle_id)) is None
        assert session.scalar(select(TrainingBlock).where(TrainingBlock.id == block_id)) is None
        assert (
            session.scalar(select(PlannedWorkout).where(PlannedWorkout.id == planned_id))
            is None
        )
        assert session.scalar(select(WorkoutLog).where(WorkoutLog.id == log_id)) is None
        assert session.scalar(select(BlockReview).where(BlockReview.id == review_id)) is None
    finally:
        session.close()


def test_pace_rule_code_is_unique(mysql_session_factory) -> None:
    session = mysql_session_factory()
    try:
        session.add_all(
            [
                PaceRule(code="R", name="短速度", sort_order=1),
                PaceRule(code="R", name="重复跑", sort_order=2),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()


def test_planned_workout_cycle_and_workout_date_are_unique(mysql_session_factory) -> None:
    session = mysql_session_factory()
    try:
        cycle = TrainingCycle(name="唯一约束测试")
        block = TrainingBlock(
            cycle=cycle,
            block_name="Week 1",
            block_type=BlockType.week,
            sort_order=1,
        )
        session.add_all(
            [
                PlannedWorkout(
                    cycle=cycle,
                    block=block,
                    workout_date=date(2026, 6, 2),
                    planned_content="轻松跑 10km",
                    sort_order=1,
                ),
                PlannedWorkout(
                    cycle=cycle,
                    block=block,
                    workout_date=date(2026, 6, 2),
                    planned_content="恢复跑 8km",
                    sort_order=2,
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()

