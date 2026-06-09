from __future__ import annotations

import os
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.config import get_settings
from planner_core.database.base import Base
from server.api.deps import get_db
from server.main import app


@pytest.fixture(scope="module")
def mysql_session_factory():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = f"gaitlogic_planner_feedback_test_{uuid4().hex[:12]}"

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
        pytest.skip(f"MySQL is not available for feedback integration tests: {exc}")

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
        pytest.skip(f"MySQL feedback tests could not start: {exc}")
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


@pytest.fixture()
def client(mysql_session_factory, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-feedback-suite")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_DAYS", "7")
    get_settings.cache_clear()

    def override_get_db():
        session = mysql_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def register_and_login(client: TestClient, username: str) -> str:
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}@example.com",
        },
    )
    assert register_response.status_code == 200
    login_response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_feedback_requires_login() -> None:
    response = TestClient(app).post(
        "/api/feedback",
        json={"feedback_type": "bug", "content": "这里看不懂"},
    )
    assert response.status_code == 401


def test_submit_feedback(client: TestClient) -> None:
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    response = client.post(
        "/api/feedback",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "feedback_type": "bug",
            "page_url": "/dashboard",
            "content": "这里的完成率我看不懂",
            "contact": "runner@example.com",
        },
    )
    assert response.status_code == 201
    assert response.json() == {"message": "反馈提交成功"}


def test_user_only_sees_own_feedback(client: TestClient) -> None:
    token_a = register_and_login(client, f"user_{uuid4().hex[:8]}")
    token_b = register_and_login(client, f"user_{uuid4().hex[:8]}")

    response_a = client.post(
        "/api/feedback",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"feedback_type": "suggestion", "page_url": "/today", "content": "A 的反馈"},
    )
    response_b = client.post(
        "/api/feedback",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"feedback_type": "bug", "page_url": "/workouts", "content": "B 的反馈"},
    )
    assert response_a.status_code == 201
    assert response_b.status_code == 201

    my_response = client.get("/api/feedback/my", headers={"Authorization": f"Bearer {token_a}"})
    assert my_response.status_code == 200
    items = my_response.json()
    assert len(items) == 1
    assert items[0]["content"] == "A 的反馈"


def test_dashboard_no_data_does_not_error(client: TestClient) -> None:
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    response = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["workout_count"] == 0
    assert float(body["planned_distance_km"]) == 0
    assert float(body["actual_distance_km"]) == 0
