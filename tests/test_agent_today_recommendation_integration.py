import json

from sqlalchemy import event, func, select

from planner_core.config import Settings
from planner_core.database.models import (
    ExternalSyncJob,
    PlannedWorkout,
    RunnerStateSnapshotRecord,
    RunnerStateSnapshotTriggerReceipt,
    TrainingCycle,
    WorkoutLog,
)
from server.agent.enums import AgentIntent
from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway
from server.schemas.coach_agent import CoachQueryRequest
from server.services.coach_agent_query_service import CoachAgentQueryService
from server.services.coach_agent_usage_service import CoachAgentRateLimiter
from tests.agent_tool_fakes import NOW
from tests.test_agent_training_integration import make_database
from tests.test_agent_provider_gateway import FakeClient, response


def disabled_settings() -> Settings:
    return Settings(
        _env_file=None,
        coach_agent_enabled=False,
        coach_agent_api_key=None,
        coach_agent_cooldown_seconds=0,
    )


def test_disabled_provider_still_returns_readonly_deterministic_today_result() -> None:
    engine, factory = make_database()
    writes = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    models = [
        TrainingCycle, PlannedWorkout, WorkoutLog, RunnerStateSnapshotRecord,
        RunnerStateSnapshotTriggerReceipt, ExternalSyncJob,
    ]
    with factory() as db:
        before = {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in models}
        result = CoachAgentQueryService(
            db,
            settings=disabled_settings(),
            rate_limiter=CoachAgentRateLimiter(daily_limit=10, cooldown_seconds=0),
            clock=lambda: NOW,
        ).query(
            user_id=901,
            payload=CoachQueryRequest(
                message="今天跑什么？",
                intent=AgentIntent.TODAY_RECOMMENDATION,
            ),
        )
        after = {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in models}
    assert result.status == "DEGRADED"
    assert result.provider_status == "DISABLED"
    assert result.today_recommendation is not None
    assert before == after
    assert writes == []


def test_public_response_and_provider_path_do_not_expose_identity_or_training_payload() -> None:
    _engine, factory = make_database()
    with factory() as db:
        result = CoachAgentQueryService(
            db,
            settings=disabled_settings(),
            rate_limiter=CoachAgentRateLimiter(daily_limit=10, cooldown_seconds=0),
            clock=lambda: NOW,
        ).query(
            user_id=902,
            payload=CoachQueryRequest(message="Explain training state", intent=AgentIntent.EXPLAIN_RUNNER_STATE),
        )
    serialized = result.model_dump_json().lower()
    for forbidden in ("user_id", "email", "phone", "garmin", "snapshot_payload", "system prompt"):
        assert forbidden not in serialized


def test_unknown_provider_evidence_id_degrades_without_public_id_leakage() -> None:
    _engine, factory = make_database()
    payload = {
        "answer": "Use the existing plan.",
        "summary": "Use the plan.",
        "key_evidence_ids": ["evidence_99"],
    }
    fake = FakeClient([response(content=json.dumps(payload))])
    configured = Settings(
        _env_file=None,
        coach_agent_enabled=True,
        coach_agent_api_key="fictional-key",
        coach_agent_base_url="https://api.example.test/v1",
        coach_agent_model="fictional-model",
        coach_agent_cooldown_seconds=0,
    )
    gateway = OpenAICompatibleAgentGateway(
        configured,
        client_factory=lambda _settings, _url: fake,
    )
    with factory() as db:
        result = CoachAgentQueryService(
            db,
            settings=configured,
            gateway=gateway,
            rate_limiter=CoachAgentRateLimiter(daily_limit=10, cooldown_seconds=0),
            clock=lambda: NOW,
        ).query(
            user_id=903,
            payload=CoachQueryRequest(
                message="Give a fictional recommendation.",
                intent=AgentIntent.TODAY_RECOMMENDATION,
            ),
        )
    assert result.status == "DEGRADED"
    serialized = result.model_dump_json()
    assert "evidence_99" not in serialized
    assert "key_evidence_ids" not in serialized
