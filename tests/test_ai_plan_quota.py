from __future__ import annotations

import json
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
from planner_core.database.models import AIPlanQuota
from server.api.deps import get_db
from server.main import app
from server.services.ai_plan_service import DeepSeekResult


@pytest.fixture(scope="module")
def mysql_session_factory():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = f"gaitlogic_planner_ai_plan_test_{uuid4().hex[:12]}"

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
        pytest.skip(f"MySQL is not available for AI plan integration tests: {exc}")

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
        pytest.skip(f"MySQL AI plan tests could not start: {exc}")
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
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-ai-plan-suite")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_DAYS", "7")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("AI_PLAN_DAILY_LIMIT", "3")
    monkeypatch.setenv("AI_PLAN_COOLDOWN_SECONDS", "60")
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


def request_payload(note: str = "标准") -> dict:
    return {
        "runner_level": "advanced",
        "recent_pb_distance": "5000m",
        "recent_pb_result": "16:24",
        "current_weekly_mileage_km": 80,
        "recent_4w_avg_mileage_km": 76,
        "available_training_days_per_week": 6,
        "can_double_run": False,
        "fixed_rest_days": ["周一"],
        "injury_notes": "无",
        "training_preferences": note,
        "target_race_name": "眉山东坡半马",
        "target_race_date": "2026-11-08",
        "target_distance": "half_marathon",
        "target_result": "1:11:30",
        "plan_start_date": "2026-06-01",
        "plan_weeks": 2,
        "intensity_style": "standard",
        "include_pace_guidance": True,
    }


def ai_output() -> str:
    return json.dumps(
        {
            "title": f"AI 半马计划 {uuid4().hex[:6]}",
            "goal": "半马 1:11:30",
            "start_date": "2026-06-01",
            "end_date": "2026-06-14",
            "target_race_name": "眉山东坡半马",
            "target_race_date": "2026-11-08",
            "target_result": "1:11:30",
            "summary": "稳步推进",
            "risk_notes": ["注意恢复"],
            "weeks": [
                {
                    "block_name": "Week 1",
                    "phase_name": "基础期",
                    "focus": "恢复接量",
                    "planned_distance_km": 80,
                    "workouts": [
                        {
                            "date": "2026-06-01",
                            "weekday": "周一",
                            "planned_content": "轻松跑 10km",
                            "focus_note": "控制心率",
                            "planned_distance_km": 10,
                            "main_type": "E",
                            "target_pace_text": "4:40-5:20/km",
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )


def mock_deepseek(monkeypatch) -> None:
    def fake_call(prompt: str) -> DeepSeekResult:
        return DeepSeekResult(content=ai_output(), input_tokens=100, output_tokens=200, total_tokens=300)

    monkeypatch.setattr("server.services.ai_plan_service.call_deepseek", fake_call)


def test_same_input_hits_cache(client: TestClient, monkeypatch) -> None:
    mock_deepseek(monkeypatch)
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    payload = request_payload()

    first = client.post("/api/ai-plan/generate", headers=headers, json=payload)
    second = client.post("/api/ai-plan/generate", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["draft_id"] == second.json()["draft_id"]


def test_cooldown_limit(client: TestClient, monkeypatch) -> None:
    mock_deepseek(monkeypatch)
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post("/api/ai-plan/generate", headers=headers, json=request_payload("A"))
    second = client.post("/api/ai-plan/generate", headers=headers, json=request_payload("B"))

    assert first.status_code == 201
    assert second.status_code == 429


def test_daily_quota_limit(client: TestClient, mysql_session_factory, monkeypatch) -> None:
    monkeypatch.setenv("AI_PLAN_DAILY_LIMIT", "1")
    monkeypatch.setenv("AI_PLAN_COOLDOWN_SECONDS", "0")
    get_settings.cache_clear()
    mock_deepseek(monkeypatch)
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post("/api/ai-plan/generate", headers=headers, json=request_payload("A"))
    second = client.post("/api/ai-plan/generate", headers=headers, json=request_payload("B"))

    assert first.status_code == 201
    assert second.status_code == 429


def test_quota_used_once_for_cached_input(client: TestClient, mysql_session_factory, monkeypatch) -> None:
    monkeypatch.setenv("AI_PLAN_COOLDOWN_SECONDS", "60")
    get_settings.cache_clear()
    mock_deepseek(monkeypatch)
    token = register_and_login(client, f"user_{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post("/api/ai-plan/generate", headers=headers, json=request_payload("cache"))
    second = client.post("/api/ai-plan/generate", headers=headers, json=request_payload("cache"))
    assert first.status_code == 201
    assert second.status_code == 201

    session = mysql_session_factory()
    try:
        quota = session.scalar(select(AIPlanQuota).order_by(AIPlanQuota.id.desc()))
        assert quota is not None
        assert quota.used_count == 1
    finally:
        session.close()
