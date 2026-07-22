from __future__ import annotations

from types import SimpleNamespace

import pytest

from planner_core.config import Settings
from planner_core.enums import WorkoutMainTypeNormalized
from server.agent.enums import AgentIntent, AgentRiskLevel
from server.agent.gateway import MockAgentLLMGateway
from server.agent.schemas import AgentModelOutput, AgentNotice, AgentTodayRecommendation
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.schemas.coach_agent import CoachQueryRequest
from server.services.coach_agent_query_service import CoachAgentQueryService
from server.services.coach_agent_usage_service import CoachAgentRateLimiter
from server.common.exceptions import TooManyRequestsError
from tests.agent_tool_fakes import FakeDependencies, NOW


def settings(**updates) -> Settings:
    values = {
        "COACH_AGENT_ENABLED": True,
        "COACH_AGENT_API_KEY": "fictional-key",
        "COACH_AGENT_BASE_URL": "https://api.example.com/v1",
        "COACH_AGENT_MODEL": "fictional-model",
        "COACH_AGENT_COOLDOWN_SECONDS": 0,
    }
    values.update({key.upper(): value for key, value in updates.items()})
    return Settings(_env_file=None, **values)


def configured_dependencies() -> FakeDependencies:
    deps = FakeDependencies()
    workout = SimpleNamespace(
        main_type_normalized=WorkoutMainTypeNormalized.easy,
        planned_content="Fictional easy run",
        planned_distance_km=None,
        target_pace_text=None,
        focus_note="Fictional focus",
        workout_log=None,
    )
    deps.today = (NOW.date(), SimpleNamespace(id=1), [workout])
    deps.evaluation = SimpleNamespace(
        data_limited=False,
        validation_status="passed",
        summary=SimpleNamespace(blocking=0, high=0, caution=0),
        evaluation=SimpleNamespace(
            matched_rules=[
                SimpleNamespace(
                    rule_code="FICTIONAL_RULE", severity="info", action="show_info",
                    explanation="Existing evidence.", output={"evidence": ["existing_metric"]},
                )
            ]
        ),
        message="Existing evidence.",
    )
    return deps


def model_output() -> AgentModelOutput:
    return AgentModelOutput(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        answer="Proceed with the existing fictional plan.",
        summary="Proceed with the existing plan.",
        risk_level=AgentRiskLevel.UNKNOWN,
        limitations=[AgentNotice(code="DATA_LIMITED", message="Some fields are unavailable.")],
        today_recommendation=AgentTodayRecommendation(
            decision="PROCEED",
            planned_workout_status="PLANNED",
            headline="Proceed with the existing fictional plan.",
            key_evidence=["FICTIONAL_RULE"],
            data_quality="UNKNOWN",
        ),
    )


def service(monkeypatch, *, gateway=None, configured=None, deps=None, recorder=None):
    dependencies = deps or configured_dependencies()
    monkeypatch.setattr(
        CoachAgentToolDependencies,
        "from_session",
        classmethod(lambda cls, db: dependencies),
    )
    return CoachAgentQueryService(
        object(),
        settings=configured or settings(),
        gateway=gateway,
        rate_limiter=CoachAgentRateLimiter(daily_limit=30, cooldown_seconds=0),
        usage_recorder=recorder,
        clock=lambda: NOW,
    )


def test_service_builds_server_identity_and_returns_provider_success(monkeypatch) -> None:
    deps = configured_dependencies()
    result = service(monkeypatch, gateway=MockAgentLLMGateway(model_output()), deps=deps).query(
        user_id=1301,
        payload=CoachQueryRequest(message="What should I run today?", intent=AgentIntent.TODAY_RECOMMENDATION),
    )
    assert result.status == "SUCCEEDED"
    assert result.provider_status == "SUCCEEDED"
    assert result.today_recommendation.decision == "PROCEED"
    assert set(deps.seen_user_ids) == {1301}
    assert "user_id" not in result.model_dump_json()


def test_provider_failure_and_disabled_provider_use_deterministic_fallback(monkeypatch) -> None:
    failed = service(
        monkeypatch,
        gateway=MockAgentLLMGateway(model_output(), error=RuntimeError("private provider detail")),
    ).query(
        user_id=1302,
        payload=CoachQueryRequest(message="今天跑什么？", intent=AgentIntent.TODAY_RECOMMENDATION),
    )
    assert failed.status == "DEGRADED"
    assert failed.provider_status == "FAILED"
    assert failed.today_recommendation.decision == "PROCEED"
    assert "private provider detail" not in failed.model_dump_json()

    disabled = service(
        monkeypatch,
        configured=settings(coach_agent_enabled=False),
    ).query(
        user_id=1303,
        payload=CoachQueryRequest(message="今天跑什么？", intent=AgentIntent.TODAY_RECOMMENDATION),
    )
    assert disabled.status == "DEGRADED"
    assert disabled.provider_status == "DISABLED"


def test_unsupported_weekly_intent_loads_no_dependencies_or_model(monkeypatch) -> None:
    deps = configured_dependencies()
    gateway = MockAgentLLMGateway(model_output())
    result = service(monkeypatch, gateway=gateway, deps=deps).query(
        user_id=1304,
        payload=CoachQueryRequest(message="Review this week", intent=AgentIntent.WEEKLY_REVIEW),
    )
    assert result.status == "REJECTED"
    assert result.provider_status == "NOT_CALLED"
    assert gateway.call_count == 0
    assert deps.seen_user_ids == []


def test_optional_intent_is_inferred_server_side(monkeypatch) -> None:
    result = service(monkeypatch, gateway=MockAgentLLMGateway(model_output())).query(
        user_id=1305,
        payload=CoachQueryRequest(message="What should I run today?"),
    )
    assert result.intent == AgentIntent.TODAY_RECOMMENDATION


def test_tool_failure_degrades_instead_of_claiming_complete_data(monkeypatch) -> None:
    deps = configured_dependencies()

    def fail(_user_id: int):
        raise RuntimeError("private database detail")

    setattr(deps, "current_runner_state", fail)
    result = service(monkeypatch, gateway=MockAgentLLMGateway(model_output()), deps=deps).query(
        user_id=1306,
        payload=CoachQueryRequest(message="today", intent=AgentIntent.TODAY_RECOMMENDATION),
    )
    assert result.status == "DEGRADED"
    assert result.limitations


def test_usage_recorder_receives_only_safe_operational_fields(monkeypatch) -> None:
    class Recorder:
        def __init__(self):
            self.kwargs = None

        def record(self, **kwargs):
            self.kwargs = kwargs

    recorder = Recorder()
    service(monkeypatch, gateway=MockAgentLLMGateway(model_output()), recorder=recorder).query(
        user_id=1307,
        payload=CoachQueryRequest(message="private fictional prompt", intent=AgentIntent.TODAY_RECOMMENDATION),
    )
    assert set(recorder.kwargs) == {"provider", "model", "usage", "status"}
    assert "private fictional prompt" not in str(recorder.kwargs)


def test_usage_failure_does_not_change_answer(monkeypatch) -> None:
    class BrokenRecorder:
        def record(self, **_kwargs):
            raise RuntimeError("usage backend unavailable")

    result = service(
        monkeypatch,
        gateway=MockAgentLLMGateway(model_output()),
        recorder=BrokenRecorder(),
    ).query(
        user_id=1308,
        payload=CoachQueryRequest(message="today", intent=AgentIntent.TODAY_RECOMMENDATION),
    )
    assert result.status == "SUCCEEDED"


def test_quota_failure_happens_before_context_or_provider(monkeypatch) -> None:
    class RejectingLimiter:
        def check_and_consume(self, _user_id: int) -> None:
            raise TooManyRequestsError("fictional quota reached")

    deps = configured_dependencies()
    gateway = MockAgentLLMGateway(model_output())
    result_service = service(monkeypatch, gateway=gateway, deps=deps)
    result_service.rate_limiter = RejectingLimiter()
    with pytest.raises(TooManyRequestsError):
        result_service.query(
            user_id=1309,
            payload=CoachQueryRequest(
                message="today",
                intent=AgentIntent.TODAY_RECOMMENDATION,
            ),
        )
    assert gateway.call_count == 0
    assert deps.seen_user_ids == []
