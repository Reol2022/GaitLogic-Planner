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
    database = f"gaitlogic_planner_auth_test_{uuid4().hex[:12]}"

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
        pytest.skip(f"MySQL is not available for auth integration tests: {exc}")

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
        pytest.skip(f"MySQL auth tests could not start: {exc}")
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
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-auth-suite")
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


def register_user(client: TestClient, username: str) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}@example.com",
            "nickname": username,
        },
    )
    assert response.status_code == 200


def login_user(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    return body["access_token"]


def test_register_login_and_me(client: TestClient) -> None:
    username = f"user_{uuid4().hex[:8]}"
    register_user(client, username)
    token = login_user(client, username)

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == username


def test_user_cannot_access_other_users_training_cycle(client: TestClient) -> None:
    user_a = f"user_{uuid4().hex[:8]}"
    user_b = f"user_{uuid4().hex[:8]}"
    register_user(client, user_a)
    register_user(client, user_b)
    token_a = login_user(client, user_a)
    token_b = login_user(client, user_b)

    create_response = client.post(
        "/api/training-cycles",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "A 的训练周期"},
    )
    assert create_response.status_code == 201
    cycle_id = create_response.json()["id"]

    forbidden_response = client.get(
        f"/api/training-cycles/{cycle_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden_response.status_code == 404

