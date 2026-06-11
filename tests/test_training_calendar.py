from __future__ import annotations

from datetime import date
import os
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.base import Base
from planner_core.database.models import PlannedWorkout, TrainingBlock, TrainingCycle, UserAccount, WorkoutLog
from planner_core.enums import BlockType, WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.api.deps import get_current_user, get_db
from server.main import app


@pytest.fixture(scope="module")
def mysql_session_factory():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = f"gaitlogic_planner_calendar_test_{uuid4().hex[:12]}"

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
        pytest.skip(f"MySQL is not available for calendar integration tests: {exc}")

    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    connection.close()

    url = f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}?charset=utf8mb4"
    engine = create_engine(url, pool_pre_ping=True, future=True)
    try:
        Base.metadata.create_all(bind=engine)
        yield sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    except OperationalError as exc:
        pytest.skip(f"MySQL calendar tests could not start: {exc}")
    finally:
        engine.dispose()
        cleanup = pymysql.connect(host=host, port=port, user=user, password=password, charset="utf8mb4", autocommit=True)
        with cleanup.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cleanup.close()


@pytest.fixture()
def calendar_client(mysql_session_factory):
    session = mysql_session_factory()
    user_a = UserAccount(username=f"user_a_{uuid4().hex[:8]}", password_hash="test-hash")
    user_b = UserAccount(username=f"user_b_{uuid4().hex[:8]}", password_hash="test-hash")
    session.add_all([user_a, user_b])
    session.flush()
    seed_user_calendar(session, user_a, include_completed=True)
    seed_user_calendar(session, user_b, include_completed=False)
    session.commit()
    user_a_id = user_a.id
    session.close()

    def override_get_db():
        db = mysql_session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        db = mysql_session_factory()
        try:
            return db.get(UserAccount, user_a_id)
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def seed_user_calendar(session: Session, user: UserAccount, *, include_completed: bool) -> None:
    cycle = TrainingCycle(user=user, name="2026 夏训", start_date=date(2026, 6, 1), end_date=date(2026, 6, 30))
    block = TrainingBlock(user=user, cycle=cycle, block_name="Week 1", block_type=BlockType.week, sort_order=1)
    completed_status = WorkoutStatusNormalized.completed_normal if include_completed else WorkoutStatusNormalized.missed
    session.add_all(
        [
            PlannedWorkout(
                user=user,
                cycle=cycle,
                block=block,
                workout_date=date(2026, 6, 2),
                weekday="周二",
                planned_content="E 12km + 4×100m",
                planned_distance_km=12,
                main_type_normalized=WorkoutMainTypeNormalized.easy,
                sort_order=1,
                workout_log=WorkoutLog(
                    user=user,
                    status_normalized=completed_status,
                    actual_distance_km=12.3 if include_completed else 0,
                    avg_pace_seconds_per_km=285,
                    avg_heart_rate=145,
                    rpe=4,
                    review_note="轻松完成",
                    completion_rate=1.02 if include_completed else 0,
                ),
            ),
            PlannedWorkout(
                user=user,
                cycle=cycle,
                block=block,
                workout_date=date(2026, 6, 4),
                weekday="周四",
                planned_content="T 8km",
                planned_distance_km=8,
                main_type_normalized=WorkoutMainTypeNormalized.tempo,
                sort_order=2,
                workout_log=WorkoutLog(user=user, status_normalized=WorkoutStatusNormalized.missed),
            ),
        ]
    )


def test_calendar_returns_month_data(calendar_client: TestClient) -> None:
    response = calendar_client.get("/api/training-calendar?month=2026-06")
    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2026-06"
    assert len(body["days"]) == 30
    assert body["summary"]["planned_distance_km"] == "20.00"


def test_calendar_only_returns_current_user_data(calendar_client: TestClient) -> None:
    response = calendar_client.get("/api/training-calendar?month=2026-06")
    body = response.json()
    june_second = next(day for day in body["days"] if day["date"] == "2026-06-02")
    assert june_second["status_normalized"] == "completed_normal"
    assert june_second["actual_distance_km"] == "12.30"


def test_calendar_status_and_empty_days(calendar_client: TestClient) -> None:
    response = calendar_client.get("/api/training-calendar?month=2026-06")
    body = response.json()
    june_fourth = next(day for day in body["days"] if day["date"] == "2026-06-04")
    june_fifth = next(day for day in body["days"] if day["date"] == "2026-06-05")
    assert june_fourth["status_normalized"] == "missed"
    assert june_fifth["planned_workout_id"] is None
    assert june_fifth["status_normalized"] == "rest"
