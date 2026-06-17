from __future__ import annotations

import os
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.config import get_settings
from planner_core.database.base import Base
from planner_core.database.models import UserAccount
from server.api.deps import get_db
from server.main import app


@pytest.fixture(scope="module")
def mysql_session_factory():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = f"gaitlogic_planner_usage_event_test_{uuid4().hex[:12]}"

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
        pytest.skip(f"MySQL is not available for usage event tests: {exc}")

    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
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
        pytest.skip(f"MySQL usage event tests could not start: {exc}")
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
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-usage-event-suite")
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
        json={"username": username, "password": "password123", "email": f"{username}@example.com"},
    )
    assert register_response.status_code == 200
    login_response = client.post("/api/auth/login", json={"username": username, "password": "password123"})
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def promote_to_admin(mysql_session_factory, username: str) -> None:
    session = mysql_session_factory()
    try:
        user = session.scalar(select(UserAccount).where(UserAccount.username == username))
        assert user is not None
        user.role = "admin"
        session.commit()
    finally:
        session.close()


def test_usage_event_requires_login() -> None:
    response = TestClient(app).post("/api/usage-events", json={"event_name": "today_viewed"})
    assert response.status_code == 401


def test_illegal_event_name_is_rejected(client: TestClient) -> None:
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    response = client.post(
        "/api/usage-events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_name": "free_text_event"},
    )
    assert response.status_code == 422


def test_sensitive_metadata_is_rejected(client: TestClient) -> None:
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    response = client.post(
        "/api/usage-events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_name": "today_viewed", "metadata_json": {"token": "secret"}},
    )
    assert response.status_code == 400


def test_normal_user_cannot_access_product_metrics(client: TestClient) -> None:
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    response = client.get("/api/admin/product-metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_product_metrics_are_aggregated(client: TestClient, mysql_session_factory) -> None:
    username = f"admin_{uuid4().hex[:8]}"
    token = register_and_login(client, username)
    promote_to_admin(mysql_session_factory, username)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/api/usage-events", headers=headers, json={"event_name": "onboarding_viewed"}).status_code == 200
    assert client.post("/api/usage-events", headers=headers, json={"event_name": "ai_plan_generate_succeeded"}).status_code == 200
    assert client.post("/api/usage-events", headers=headers, json={"event_name": "ai_plan_applied"}).status_code == 200
    response = client.get("/api/admin/product-metrics", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_viewed_users"] == 1
    assert body["ai_plan_generate_succeeded_users"] == 1
    assert body["ai_plan_applied_users"] == 1
    assert body["generate_to_apply_rate"] == 1
