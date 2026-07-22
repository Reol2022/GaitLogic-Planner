from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, DefaultClause, create_engine, event, func, select, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.base import Base
from planner_core.database.models import (
    ExternalSyncJob,
    PlannedWorkout,
    RunnerStateSnapshotRecord,
    RunnerStateSnapshotTriggerReceipt,
    TrainingCycle,
    UserAccount,
    WorkoutLog,
)
from planner_core.enums import WorkoutStatusNormalized
from server.agent.enums import AgentIntent, AgentRiskLevel, AgentRunStatus, AgentToolStatus
from server.agent.gateway import MockAgentLLMGateway
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.schemas import AgentContext, AgentModelOutput, AgentRequest
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.factory import build_coach_agent_tool_registry
from server.agent.training_context_builder import AgentTrainingContextBuilder
from tests.agent_tool_fakes import NOW


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


def make_database():
    engine = create_engine("sqlite:///:memory:", future=True)
    mysql_only_defaults = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.server_default is not None and "ON UPDATE" in str(column.server_default.arg):
                mysql_only_defaults.append((column, column.server_default))
                column.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
    try:
        Base.metadata.create_all(engine)
    finally:
        for column, default in mysql_only_defaults:
            column.server_default = default
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as db:
        db.add_all(
            [
                UserAccount(id=901, username="fictional-a", password_hash="x", status="active"),
                UserAccount(id=902, username="fictional-b", password_hash="x", status="active"),
                WorkoutLog(
                    id=9101, user_id=901, activity_date=date(2026, 7, 21),
                    status_normalized=WorkoutStatusNormalized.completed_normal,
                    actual_distance_km=8, actual_duration_seconds=3000, rpe=4,
                    workout_type="easy", source_type="garmin", is_unplanned=True,
                ),
                WorkoutLog(
                    id=9102, user_id=902, activity_date=date(2026, 7, 21),
                    status_normalized=WorkoutStatusNormalized.completed_normal,
                    actual_distance_km=42, actual_duration_seconds=12000, rpe=8,
                    workout_type="long_run", source_type="manual", is_unplanned=True,
                ),
            ]
        )
        db.commit()
    return engine, factory


def agent_context(user_id: int, intent: AgentIntent) -> AgentContext:
    request = AgentRequest(user_id=user_id, message="fictional", intent=intent)
    return AgentContext(request_id=request.request_id, user_id=user_id, intent=intent, current_time=NOW, timezone="Asia/Shanghai")


def test_two_users_are_isolated_and_tool_chain_issues_only_selects() -> None:
    engine, factory = make_database()
    writes: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def reject_writes(_conn, _cursor, statement, _parameters, _context, _executemany):
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)
            raise AssertionError("read-only agent tool attempted a database write")

    with factory() as db:
        registry = build_coach_agent_tool_registry(CoachAgentToolDependencies.from_session(db))
        first = registry.invoke("get_recent_training", {"days": 7, "limit": 20}, agent_context(901, AgentIntent.WEEKLY_REVIEW))
        second = registry.invoke("get_recent_training", {"days": 7, "limit": 20}, agent_context(902, AgentIntent.WEEKLY_REVIEW))
        assert first.status == second.status == AgentToolStatus.SUCCEEDED
        assert first.data["summary"]["total_distance_km"] == 8.0
        assert second.data["summary"]["total_distance_km"] == 42.0
        assert "user_id" not in str(first.data)
    assert writes == []


def test_readonly_tools_preserve_key_table_counts() -> None:
    engine, factory = make_database()
    models = [TrainingCycle, PlannedWorkout, WorkoutLog, RunnerStateSnapshotRecord, RunnerStateSnapshotTriggerReceipt, ExternalSyncJob]
    with factory() as db:
        before = {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in models}
        registry = build_coach_agent_tool_registry(CoachAgentToolDependencies.from_session(db))
        for name, args in (
            ("get_recent_training", {"days": 7, "limit": 20}),
            ("get_training_data_quality", {"window_days": 14}),
            ("get_today_workout", {}),
            ("get_current_training_cycle", {}),
            ("get_runner_state_history", {"limit": 7}),
        ):
            result = registry.invoke(name, args, agent_context(901, AgentIntent.WEEKLY_REVIEW))
            assert result.status in {AgentToolStatus.SUCCEEDED, AgentToolStatus.NOT_ALLOWED}
        after = {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in models}
    assert before == after


def test_daily_rule_evaluation_readonly_path_does_not_persist() -> None:
    engine, factory = make_database()
    writes: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_writes(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    with factory() as db:
        registry = build_coach_agent_tool_registry(CoachAgentToolDependencies.from_session(db))
        result = registry.invoke(
            "evaluate_today_workout",
            {},
            agent_context(901, AgentIntent.TODAY_RECOMMENDATION),
        )
        assert result.status == AgentToolStatus.SUCCEEDED
    assert writes == []


def test_orchestrator_uses_preloaded_context_without_real_provider() -> None:
    _engine, factory = make_database()
    with factory() as db:
        registry = build_coach_agent_tool_registry(CoachAgentToolDependencies.from_session(db))
        builder = AgentTrainingContextBuilder(registry=registry, clock=lambda: NOW)
        gateway = MockAgentLLMGateway(
            AgentModelOutput(
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                answer="Fictional deterministic explanation.",
                risk_level=AgentRiskLevel.UNKNOWN,
            )
        )
        agent = GaitLogicCoachAgent(gateway=gateway, registry=registry, context_builder=builder)
        response = agent.run(
            AgentRequest(user_id=901, message="Explain the fictional state", intent=AgentIntent.EXPLAIN_RUNNER_STATE)
        )
        assert response.status == AgentRunStatus.SUCCEEDED
        assert gateway.call_count == 1
        assert agent.last_context is not None
        assert agent.last_context.runner_state is not None
