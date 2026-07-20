from __future__ import annotations

from datetime import date
import os
from decimal import Decimal
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.base import Base
from planner_core.database.models import PlannedWorkout, TrainingBlock, TrainingCycle, UserAccount, WorkoutLog
from planner_core.enums import BlockType, WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.schemas.workout_import import NormalizedWorkoutActivity, WorkoutImportStructuredRequest
from server.services import workout_import_service


@pytest.fixture(scope="module")
def mysql_session_factory():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = f"gaitlogic_workout_import_test_{uuid4().hex[:10]}"

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
        pytest.skip(f"MySQL is not available for workout import tests: {exc}")

    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    connection.close()

    url = f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}?charset=utf8mb4"
    engine = create_engine(url, pool_pre_ping=True, future=True)
    try:
        Base.metadata.create_all(bind=engine)
        yield sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    except OperationalError as exc:
        pytest.skip(f"MySQL workout import tests could not start: {exc}")
    finally:
        engine.dispose()
        cleanup = pymysql.connect(host=host, port=port, user=user, password=password, charset="utf8mb4", autocommit=True)
        with cleanup.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cleanup.close()


def create_user_graph(db: Session) -> tuple[UserAccount, PlannedWorkout]:
    user = UserAccount(username=f"runner_{uuid4().hex[:8]}", password_hash="hash")
    cycle = TrainingCycle(user=user, name="夏训", start_date=date(2026, 7, 1), end_date=date(2026, 7, 31))
    block = TrainingBlock(
        user=user,
        cycle=cycle,
        block_name="Week 1",
        block_type=BlockType.week,
        sort_order=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 7),
    )
    workout = PlannedWorkout(
        user=user,
        cycle=cycle,
        block=block,
        workout_date=date(2026, 7, 1),
        session_index=1,
        planned_content="有氧跑 12km",
        planned_distance_km=Decimal("12.00"),
        main_type_raw="E",
        main_type_normalized=WorkoutMainTypeNormalized.easy,
        sort_order=1,
    )
    db.add(workout)
    db.commit()
    return user, workout


def test_workout_import_request_rejects_empty_activities() -> None:
    with pytest.raises(ValidationError):
        WorkoutImportStructuredRequest(client_request_id="empty", activities=[])


def test_normalized_activity_rejects_rpe_out_of_range() -> None:
    with pytest.raises(ValidationError):
        NormalizedWorkoutActivity(activity_date=date(2026, 7, 1), rpe=11)


def test_normalized_activity_allows_double_run_session_index() -> None:
    morning = NormalizedWorkoutActivity(activity_date=date(2026, 7, 1), session_index=1, distance_km=Decimal("12.30"))
    evening = NormalizedWorkoutActivity(activity_date=date(2026, 7, 1), session_index=2, distance_km=Decimal("6.20"))
    assert morning.session_index == 1
    assert evening.session_index == 2


def test_structured_import_creates_draft_and_is_idempotent(mysql_session_factory) -> None:
    db = mysql_session_factory()
    try:
        user, workout = create_user_graph(db)
        payload = WorkoutImportStructuredRequest(
            source="external_assistant",
            client_request_id="import-1",
            activities=[
                NormalizedWorkoutActivity(
                    activity_date=date(2026, 7, 1),
                    session_index=1,
                    sport_type="running",
                    workout_type="E",
                    distance_km=Decimal("12.30"),
                    duration_seconds=3012,
                    completion_status="completed",
                )
            ],
        )
        first = workout_import_service.create_structured_import(db, user.id, payload)
        second = workout_import_service.create_structured_import(db, user.id, payload)
        assert first.batch_id == second.batch_id
        assert first.matched_plan_count == 1
        assert first.items[0].matched_plan_id == workout.id
        assert first.items[0].suggested_action == "create_log"
    finally:
        db.close()


def test_apply_creates_planned_and_unplanned_logs(mysql_session_factory) -> None:
    db = mysql_session_factory()
    try:
        user, workout = create_user_graph(db)
        payload = WorkoutImportStructuredRequest(
            source="external_assistant",
            client_request_id="import-2",
            activities=[
                NormalizedWorkoutActivity(activity_date=date(2026, 7, 1), session_index=1, distance_km=Decimal("12.30"), duration_seconds=3012),
                NormalizedWorkoutActivity(activity_date=date(2026, 7, 1), session_index=2, distance_km=Decimal("6.20"), duration_seconds=1800),
            ],
        )
        draft = workout_import_service.create_structured_import(db, user.id, payload)
        result = workout_import_service.apply_workout_import(db, user.id, draft.batch_id)
        logs = list(db.scalars(select(WorkoutLog).where(WorkoutLog.user_id == user.id)))
        assert result.created_count == 2
        assert len(logs) == 2
        assert any(log.planned_workout_id == workout.id for log in logs)
        assert any(log.is_unplanned for log in logs)
    finally:
        db.close()


def test_update_objective_fields_keeps_subjective_manual_data(mysql_session_factory) -> None:
    db = mysql_session_factory()
    try:
        user, workout = create_user_graph(db)
        log = WorkoutLog(
            user=user,
            planned_workout=workout,
            status_normalized=WorkoutStatusNormalized.completed_normal,
            actual_distance_km=Decimal("12.00"),
            rpe=4,
            review_note="后程轻松",
            source_type="manual",
        )
        db.add(log)
        db.commit()
        payload = WorkoutImportStructuredRequest(
            source="external_assistant",
            client_request_id="import-3",
            merge_strategy="update_objective_fields",
            activities=[
                NormalizedWorkoutActivity(
                    activity_date=date(2026, 7, 1),
                    session_index=1,
                    distance_km=Decimal("12.30"),
                    duration_seconds=3000,
                    rpe=8,
                    notes="导入备注",
                )
            ],
        )
        draft = workout_import_service.create_structured_import(db, user.id, payload)
        workout_import_service.apply_workout_import(db, user.id, draft.batch_id)
        db.refresh(log)
        assert log.actual_distance_km == Decimal("12.30")
        assert log.actual_duration_seconds == 3000
        assert log.rpe == 4
        assert log.review_note == "后程轻松"
    finally:
        db.close()
