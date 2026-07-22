from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.models import RunnerStateSnapshotRecord, UserAccount
from planner_core.enums import RunnerStateSnapshotTriggerType
from scripts.upgrade_v0103_runner_state_snapshots import downgrade, upgrade
from server.api.deps import get_current_user, get_db
from server.api.routes import runner_state as runner_state_routes
from server.common.exceptions import NotFoundError
from server.main import app
from server.schemas.runner_state_snapshot import (
    RunnerStateSnapshotCreateResult,
    RunnerStateSnapshotDetail,
    RunnerStateSnapshotListResponse,
    RunnerStateTimelineRange,
)
from server.services.runner_state_service import RunnerStateService, build_runner_state_snapshot
from server.services.runner_state_snapshot_serializer import (
    RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION,
    calculate_runner_state_payload_hash,
    canonicalize_runner_state_payload,
    serialize_runner_state_snapshot,
)
from server.services.runner_state_snapshot_service import RunnerStateSnapshotService
from tests.openapi_assertions import get_openapi_methods

SHANGHAI = ZoneInfo("Asia/Shanghai")


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


def _snapshot(
    runner_id: int = 701,
    *,
    cutoff: date = date(2026, 7, 15),
    generated_at: datetime | None = None,
):
    calculated = generated_at or datetime(2026, 7, 15, 18, 30, tzinfo=SHANGHAI)
    snapshot = build_runner_state_snapshot(
        runner_id=runner_id,
        cycle=None,
        log_rows=[],
        planned_workouts=[],
        generated_at=calculated,
        timezone_name="Asia/Shanghai",
        calculation_window_end=cutoff,
    )
    snapshot.recent_training.distance_7d_km = 12.5
    snapshot.recent_training.distance_28d_km = 46.75
    return snapshot


def _hash(payload: dict, *, cutoff: date = date(2026, 7, 15), ruleset: str = "rules-v1", schema: str = RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION) -> str:
    return calculate_runner_state_payload_hash(
        payload,
        data_cutoff_date=cutoff,
        ruleset_version=ruleset,
        snapshot_schema_version=schema,
    )


def test_canonical_hash_is_stable_for_dictionary_key_order() -> None:
    assert _hash({"b": 2, "a": {"d": 4, "c": 3}}) == _hash(
        {"a": {"c": 3, "d": 4}, "b": 2}
    )


def test_calculation_and_creation_times_do_not_change_hash() -> None:
    first = {
        "identity": {"generated_at": "2026-07-15T10:00:00+08:00", "runner_id": 1},
        "inference_metadata": {"calculated_at": "2026-07-15T10:00:00+08:00"},
        "created_at": "2026-07-15T10:01:00+08:00",
    }
    second = deepcopy(first)
    second["identity"]["generated_at"] = "2026-07-15T11:00:00+08:00"
    second["inference_metadata"]["calculated_at"] = "2026-07-15T11:00:00+08:00"
    second["created_at"] = "2026-07-15T11:01:00+08:00"
    assert _hash(first) == _hash(second)


@pytest.mark.parametrize(
    "field",
    ("recent_training", "evidence", "risk_flags", "data_quality"),
)
def test_semantic_snapshot_sections_change_hash(field: str) -> None:
    first = {
        "recent_training": {"distance_7d_km": 10},
        "evidence": [{"metric": "distance", "value": 10}],
        "risk_flags": [],
        "data_quality": {"confidence": 0.8},
    }
    second = deepcopy(first)
    if field == "risk_flags":
        second[field].append({"code": "VOLUME_SPIKE"})
    elif field == "evidence":
        second[field][0]["value"] = 11
    elif field == "recent_training":
        second[field]["distance_7d_km"] = 11
    else:
        second[field]["confidence"] = 0.7
    assert _hash(first) != _hash(second)


def test_versions_and_cutoff_date_change_hash() -> None:
    payload = {"state": "STABLE"}
    base = _hash(payload)
    assert base != _hash(payload, ruleset="rules-v2")
    assert base != _hash(payload, schema="runner-state-snapshot-2.0.0")
    assert base != _hash(payload, cutoff=date(2026, 7, 16))


def test_enum_date_datetime_and_decimal_are_canonicalized_stably() -> None:
    first = {
        "trigger": RunnerStateSnapshotTriggerType.MANUAL,
        "day": date(2026, 7, 15),
        "at": datetime(2026, 7, 15, 8, tzinfo=SHANGHAI),
        "distance": Decimal("12.5000"),
    }
    second = {"distance": Decimal("12.5"), "at": first["at"], "day": first["day"], "trigger": "MANUAL"}
    assert canonicalize_runner_state_payload(first) == canonicalize_runner_state_payload(second)


def test_snapshot_serialization_retains_complete_audit_times() -> None:
    snapshot = _snapshot()
    payload = serialize_runner_state_snapshot(snapshot)
    assert payload["identity"]["generated_at"] == "2026-07-15T18:30:00+08:00"
    assert payload["inference_metadata"]["calculated_at"] == "2026-07-15T18:30:00+08:00"
    assert "email" not in str(payload).lower()


@pytest.fixture()
def snapshot_database(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'snapshots.db'}", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    _create_sqlite_user_table(engine)
    with engine.begin() as connection:
        upgrade(connection)
    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    try:
        yield engine, factory
    finally:
        engine.dispose()


class _StateStub:
    def __init__(self, *snapshots) -> None:
        self.snapshots = list(snapshots)
        self.calls: list[int] = []

    def get_current(self, user: UserAccount):
        self.calls.append(int(user.id))
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]


def _create_sqlite_user_table(engine) -> None:
    # The production user table uses a MySQL-only ON UPDATE timestamp clause.
    # This compatible test table preserves the columns the ORM needs without
    # pretending SQLite is the production database.
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE user_account (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username VARCHAR(64) NOT NULL UNIQUE,
                  email VARCHAR(255) NULL UNIQUE,
                  password_hash VARCHAR(255) NOT NULL,
                  nickname VARCHAR(64) NULL,
                  avatar_url VARCHAR(512) NULL,
                  role VARCHAR(32) NOT NULL DEFAULT 'user',
                  ui_mode VARCHAR(16) NOT NULL DEFAULT 'simple',
                  status VARCHAR(32) NOT NULL DEFAULT 'active',
                  last_login_at DATETIME NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def _user(session: Session, username: str = "fictional-runner") -> UserAccount:
    user = UserAccount(username=username, password_hash="fictional-hash", status="active")
    session.add(user)
    session.commit()
    return user


def test_model_constraints_indexes_json_and_migration_round_trip(tmp_path: Path) -> None:
    table = RunnerStateSnapshotRecord.__table__
    unique_names = {item.name for item in table.constraints if item.__class__.__name__ == "UniqueConstraint"}
    index_names = {item.name for item in table.indexes}
    assert "uq_runner_state_snapshot_user_cutoff_hash" in unique_names
    assert index_names == {
        "ix_runner_state_snapshots_user_cutoff",
        "ix_runner_state_snapshots_user_created",
    }
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "CASCADE"

    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}", future=True)
    _create_sqlite_user_table(engine)
    with engine.begin() as connection:
        upgrade(connection)
        assert inspect(connection).has_table("runner_state_snapshots")
        connection.execute(
            table.insert().values(
                user_id=1,
                snapshot_date=date(2026, 7, 15),
                data_cutoff_date=date(2026, 7, 15),
                calculated_at=datetime(2026, 7, 15, 12),
                trigger_type=RunnerStateSnapshotTriggerType.MANUAL,
                snapshot_schema_version=RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION,
                ruleset_version="rules-v1",
                risk_flag_count=0,
                snapshot_payload={"state": "UNKNOWN"},
                payload_hash="a" * 64,
            )
        )
        assert connection.scalar(select(table.c.snapshot_payload))["state"] == "UNKNOWN"
        with pytest.raises(OperationalError):
            upgrade(connection)
    with engine.begin() as connection:
        downgrade(connection)
        assert not inspect(connection).has_table("runner_state_snapshots")
    engine.dispose()


def test_first_save_duplicate_and_changed_state(snapshot_database) -> None:
    _engine, factory = snapshot_database
    with factory() as session:
        user = _user(session)
        first_snapshot = _snapshot(user.id)
        later_same_state = _snapshot(
            user.id,
            generated_at=datetime(2026, 7, 15, 19, 30, tzinfo=SHANGHAI),
        )
        changed = _snapshot(user.id)
        changed.recent_training.distance_7d_km = 13.0
        stub = _StateStub(first_snapshot, later_same_state, changed)
        service = RunnerStateSnapshotService(
            session,
            runner_state_service=stub,
            clock=lambda: datetime(2026, 7, 16, 0, 30, tzinfo=SHANGHAI),
        )

        first = service.save_current(user)
        duplicate = service.save_current(user)
        changed_result = service.save_current(user)

        assert (first.created, first.duplicate) == (True, False)
        assert (duplicate.created, duplicate.duplicate) == (False, True)
        assert duplicate.snapshot.id == first.snapshot.id
        assert changed_result.created is True
        assert session.scalar(select(func_count(RunnerStateSnapshotRecord.id))) == 2
        assert first.snapshot.snapshot_date == date(2026, 7, 16)
        assert first.snapshot.calculated_at.utcoffset() == timedelta(hours=8)


def func_count(column):
    from sqlalchemy import func

    return func.count(column)


def test_different_cutoff_date_allows_same_values(snapshot_database) -> None:
    _engine, factory = snapshot_database
    with factory() as session:
        user = _user(session, "another-fictional-runner")
        service = RunnerStateSnapshotService(
            session,
            runner_state_service=_StateStub(
                _snapshot(user.id, cutoff=date(2026, 7, 15)),
                _snapshot(user.id, cutoff=date(2026, 7, 16)),
            ),
            clock=lambda: datetime(2026, 7, 15, 16, 30, tzinfo=ZoneInfo("UTC")),
        )
        first = service.save_current(user)
        assert first.created is True
        assert first.snapshot.snapshot_date == date(2026, 7, 16)
        assert service.save_current(user).created is True


def test_existing_duplicate_is_reused_across_sessions(snapshot_database) -> None:
    _engine, factory = snapshot_database
    with factory() as session, factory() as concurrent_session:
        user = _user(session, "concurrent-fictional-runner")
        snapshot = _snapshot(user.id)
        first = RunnerStateSnapshotService(
            concurrent_session,
            runner_state_service=_StateStub(snapshot),
            clock=lambda: datetime(2026, 7, 15, 20, tzinfo=SHANGHAI),
        ).save_current(concurrent_session.get(UserAccount, user.id))
        service = RunnerStateSnapshotService(
            session,
            runner_state_service=_StateStub(snapshot),
            clock=lambda: datetime(2026, 7, 15, 20, tzinfo=SHANGHAI),
        )
        result = service.save_current(user)

        assert result.duplicate is True
        assert result.snapshot.id == first.snapshot.id
        assert concurrent_session.scalar(select(func_count(RunnerStateSnapshotRecord.id))) == 1


def test_non_duplicate_integrity_error_is_not_disguised(snapshot_database, monkeypatch) -> None:
    _engine, factory = snapshot_database
    with factory() as session:
        user = _user(session, "failed-fictional-runner")
        service = RunnerStateSnapshotService(
            session,
            runner_state_service=_StateStub(_snapshot(user.id)),
        )
        error = IntegrityError("insert", {}, Exception("foreign key constraint failed"))
        monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(error))
        with pytest.raises(IntegrityError) as caught:
            service.save_current(user)
        assert caught.value is error
        assert session.scalar(select(func_count(RunnerStateSnapshotRecord.id))) == 0


def test_list_filters_orders_and_does_not_load_payload(snapshot_database) -> None:
    _engine, factory = snapshot_database
    with factory() as session:
        owner = _user(session, "history-owner")
        other = _user(session, "history-other")
        owner_service = RunnerStateSnapshotService(
            session,
            runner_state_service=_StateStub(
                _snapshot(owner.id, cutoff=date(2026, 7, 14)),
                _snapshot(owner.id, cutoff=date(2026, 7, 15)),
            ),
        )
        other_service = RunnerStateSnapshotService(
            session, runner_state_service=_StateStub(_snapshot(other.id))
        )
        owner_service.save_current(owner)
        owner_service.save_current(owner)
        other_service.save_current(other)

        result = owner_service.list_snapshots(
            user_id=owner.id,
            start_date=date(2026, 7, 14),
            end_date=date(2026, 7, 15),
            limit=30,
            offset=0,
        )
        assert result.total == 2
        assert [item.data_cutoff_date for item in result.items] == [date(2026, 7, 15), date(2026, 7, 14)]
        assert "snapshot_payload" not in result.items[0].model_dump()


def test_detail_is_user_scoped_and_user_delete_cascades(snapshot_database) -> None:
    _engine, factory = snapshot_database
    with factory() as session:
        owner = _user(session, "detail-owner")
        other = _user(session, "detail-other")
        service = RunnerStateSnapshotService(
            session, runner_state_service=_StateStub(_snapshot(owner.id))
        )
        saved = service.save_current(owner)
        assert service.get_snapshot(user_id=owner.id, snapshot_id=saved.snapshot.id).snapshot_payload
        with pytest.raises(NotFoundError):
            service.get_snapshot(user_id=other.id, snapshot_id=saved.snapshot.id)

        session.execute(text("DELETE FROM user_account WHERE id = :id"), {"id": owner.id})
        session.commit()
        assert session.scalar(select(func_count(RunnerStateSnapshotRecord.id))) == 0


def _api_detail(snapshot_id: int = 91) -> RunnerStateSnapshotDetail:
    return RunnerStateSnapshotDetail(
        id=snapshot_id,
        snapshot_date=date(2026, 7, 15),
        data_cutoff_date=date(2026, 7, 15),
        calculated_at=datetime(2026, 7, 15, 18, tzinfo=SHANGHAI),
        created_at=datetime(2026, 7, 15, 18, 1, tzinfo=SHANGHAI),
        trigger_type=RunnerStateSnapshotTriggerType.MANUAL,
        snapshot_schema_version=RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION,
        ruleset_version="runner-state-rules-1.0.0",
        distance_7d_km=12.5,
        distance_28d_km=46.75,
        volume_trend="STABLE",
        training_consistency="MODERATE",
        fatigue_state="NORMAL",
        training_phase="UNKNOWN",
        risk_flag_count=0,
        evidence_coverage=0.8,
        data_completeness=0.75,
        snapshot_payload=serialize_runner_state_snapshot(_snapshot()),
    )


def test_snapshot_post_requires_authentication() -> None:
    response = TestClient(app).post("/api/runner-state/snapshots", json={})
    assert response.status_code == 401


def test_snapshot_post_fixes_server_fields_and_rejects_forgery(monkeypatch) -> None:
    current_user = UserAccount(id=801, username="api-runner", password_hash="x", status="active")
    calls: list[int] = []

    class FakeService:
        def __init__(self, db) -> None:
            pass

        def save_current(self, user):
            calls.append(user.id)
            return RunnerStateSnapshotCreateResult(snapshot=_api_detail(), created=True, duplicate=False)

    monkeypatch.setattr(runner_state_routes, "RunnerStateSnapshotService", FakeService)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    try:
        client = TestClient(app)
        response = client.post("/api/runner-state/snapshots")
        forged = client.post(
            "/api/runner-state/snapshots",
            json={"user_id": 999, "trigger_type": "SYSTEM"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls == [801]
    assert response.json()["snapshot"]["trigger_type"] == "MANUAL"
    assert forged.status_code == 400


def test_snapshot_list_defaults_and_hides_internal_fields(monkeypatch) -> None:
    current_user = UserAccount(id=802, username="list-runner", password_hash="x", status="active")
    seen: list[dict] = []

    class FakeService:
        def __init__(self, db) -> None:
            pass

        def list_snapshots(self, **kwargs):
            seen.append(kwargs)
            item = _api_detail().model_dump(exclude={"snapshot_payload"})
            return RunnerStateSnapshotListResponse(items=[item], total=1, limit=kwargs["limit"], offset=kwargs["offset"])

    monkeypatch.setattr(runner_state_routes, "RunnerStateSnapshotService", FakeService)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    try:
        response = TestClient(app).get("/api/runner-state/snapshots")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert seen == [{"user_id": 802, "start_date": None, "end_date": None, "limit": 30, "offset": 0}]
    serialized = response.json()
    for hidden in ("snapshot_payload", "payload_hash", "user_id"):
        assert hidden not in str(serialized)


def test_snapshot_list_rejects_invalid_range_and_limit(snapshot_database) -> None:
    _engine, factory = snapshot_database
    current_user = UserAccount(id=803, username="range-runner", password_hash="x", status="active")
    with factory() as session:
        app.dependency_overrides[get_current_user] = lambda: current_user
        app.dependency_overrides[get_db] = lambda: session
        try:
            client = TestClient(app)
            invalid_range = client.get(
                "/api/runner-state/snapshots?start_date=2026-07-16&end_date=2026-07-15"
            )
            excessive_limit = client.get("/api/runner-state/snapshots?limit=101")
        finally:
            app.dependency_overrides.clear()
    assert invalid_range.status_code == 400
    assert excessive_limit.status_code == 400


def test_snapshot_detail_returns_saved_payload_without_recalculation(monkeypatch) -> None:
    current_user = UserAccount(id=804, username="detail-runner", password_hash="x", status="active")
    seen: list[tuple[int, int]] = []

    class FakeService:
        def __init__(self, db) -> None:
            pass

        def get_snapshot(self, *, user_id: int, snapshot_id: int):
            seen.append((user_id, snapshot_id))
            return _api_detail(snapshot_id)

    def forbidden_recalculation(self, user, *, generated_at=None):
        raise AssertionError("Historical detail must not recalculate current state")

    monkeypatch.setattr(runner_state_routes, "RunnerStateSnapshotService", FakeService)
    monkeypatch.setattr(RunnerStateService, "get_current", forbidden_recalculation)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    try:
        response = TestClient(app).get("/api/runner-state/snapshots/91")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert seen == [(804, 91)]
    assert response.json()["snapshot_payload"]["identity"]["runner_id"] == 701
    assert "payload_hash" not in response.text


def test_get_current_does_not_construct_snapshot_service(monkeypatch) -> None:
    current_user = UserAccount(id=805, username="current-runner", password_hash="x", status="active")

    class ForbiddenSnapshotService:
        def __init__(self, db) -> None:
            raise AssertionError("GET current must not touch snapshot persistence")

    monkeypatch.setattr(runner_state_routes, "RunnerStateSnapshotService", ForbiddenSnapshotService)
    monkeypatch.setattr(
        RunnerStateService,
        "get_current",
        lambda self, user, *, generated_at=None: _snapshot(user.id),
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    try:
        response = TestClient(app).get("/api/runner-state/current")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200


def test_snapshot_routes_do_not_offer_update_or_delete_methods() -> None:
    methods = get_openapi_methods(app, "/api/runner-state/snapshots")
    assert methods == {"GET", "POST"}


def _timeline_record(
    *,
    user_id: int,
    cutoff: date,
    created_at: datetime,
    distance_7d_km: float | None = 20,
    distance_28d_km: float | None = 80,
    risk_flags: list[dict] | None = None,
) -> RunnerStateSnapshotRecord:
    payload = serialize_runner_state_snapshot(_snapshot(user_id, cutoff=cutoff))
    payload["data_quality"]["rpe_coverage_28d"] = 0.625
    payload["data_quality"]["heart_rate_coverage_28d"] = 0.5
    payload["risk_flags"] = risk_flags or []
    identity = f"{user_id}:{cutoff.isoformat()}:{created_at.isoformat()}:{distance_7d_km}"
    return RunnerStateSnapshotRecord(
        user_id=user_id,
        snapshot_date=cutoff,
        data_cutoff_date=cutoff,
        calculated_at=created_at,
        created_at=created_at,
        trigger_type=RunnerStateSnapshotTriggerType.MANUAL,
        snapshot_schema_version=RUNNER_STATE_SNAPSHOT_SCHEMA_VERSION,
        ruleset_version="runner-state-rules-1.0.0",
        distance_7d_km=Decimal(str(distance_7d_km)) if distance_7d_km is not None else None,
        distance_28d_km=Decimal(str(distance_28d_km)) if distance_28d_km is not None else None,
        volume_trend="STABLE",
        training_consistency="HIGH",
        fatigue_state="NORMAL",
        training_phase="UNKNOWN",
        risk_flag_count=len(payload["risk_flags"]),
        evidence_coverage=Decimal("0.8"),
        data_completeness=Decimal("0.75"),
        snapshot_payload=payload,
        payload_hash=hashlib.sha256(identity.encode()).hexdigest(),
    )


def test_timeline_range_boundaries_use_natural_days_and_calendar_months() -> None:
    end = date(2026, 7, 19)
    assert RunnerStateSnapshotService._timeline_start_date(
        end, RunnerStateTimelineRange.DAYS_28
    ) == date(2026, 6, 22)
    assert RunnerStateSnapshotService._timeline_start_date(
        end, RunnerStateTimelineRange.WEEKS_12
    ) == date(2026, 4, 27)
    assert RunnerStateSnapshotService._timeline_start_date(
        end, RunnerStateTimelineRange.MONTHS_6
    ) == date(2026, 1, 19)
    assert RunnerStateSnapshotService._timeline_start_date(
        date(2024, 8, 31), RunnerStateTimelineRange.MONTHS_6
    ) == date(2024, 2, 29)


def test_timeline_selects_latest_snapshot_per_date_and_counts_all(snapshot_database) -> None:
    _engine, factory = snapshot_database
    risk = {
        "code": "VOLUME_SPIKE",
        "severity": "WARNING",
        "message": "虚构跑量提示",
        "suggested_action_type": "REVIEW",
        "triggered_rule": "volume_ratio > 1.5",
        "evidence": [],
    }
    with factory() as session:
        owner = _user(session, "timeline-owner")
        older = _timeline_record(
            user_id=owner.id,
            cutoff=date(2026, 7, 18),
            created_at=datetime(2026, 7, 18, 9),
            distance_7d_km=18,
        )
        latest = _timeline_record(
            user_id=owner.id,
            cutoff=date(2026, 7, 18),
            created_at=datetime(2026, 7, 18, 21),
            distance_7d_km=28,
            risk_flags=[risk],
        )
        previous = _timeline_record(
            user_id=owner.id,
            cutoff=date(2026, 7, 17),
            created_at=datetime(2026, 7, 17, 20),
        )
        session.add_all([older, latest, previous])
        session.commit()

        service = RunnerStateSnapshotService(
            session,
            runner_state_service=_StateStub(_snapshot(owner.id)),
            clock=lambda: datetime(2026, 7, 19, 0, 15, tzinfo=SHANGHAI),
        )
        before = (len(session.new), len(session.dirty), len(session.deleted))
        result = service.list_timeline_snapshots(
            user_id=owner.id, timeline_range=RunnerStateTimelineRange.DAYS_28
        )

        assert result.total_snapshots == 3
        assert result.days_with_snapshots == 2
        assert [item.data_cutoff_date for item in result.items] == [
            date(2026, 7, 17),
            date(2026, 7, 18),
        ]
        assert result.items[-1].id == latest.id
        assert result.items[-1].distance_7d_km == 28
        assert result.items[-1].distance_28d_weekly_average_km == 20
        assert result.items[-1].rpe_coverage_28d == 0.625
        assert result.items[-1].heart_rate_coverage_28d == 0.5
        assert result.items[-1].risk_flags[0].code.value == "VOLUME_SPIKE"
        assert (len(session.new), len(session.dirty), len(session.deleted)) == before


def test_timeline_uses_larger_id_when_created_at_matches(snapshot_database) -> None:
    _engine, factory = snapshot_database
    with factory() as session:
        owner = _user(session, "timeline-id-owner")
        timestamp = datetime(2026, 7, 18, 21)
        first = _timeline_record(
            user_id=owner.id,
            cutoff=date(2026, 7, 18),
            created_at=timestamp,
            distance_7d_km=18,
        )
        second = _timeline_record(
            user_id=owner.id,
            cutoff=date(2026, 7, 18),
            created_at=timestamp,
            distance_7d_km=22,
        )
        session.add_all([first, second])
        session.commit()
        result = RunnerStateSnapshotService(
            session,
            clock=lambda: datetime(2026, 7, 19, 12, tzinfo=SHANGHAI),
        ).list_timeline_snapshots(
            user_id=owner.id, timeline_range=RunnerStateTimelineRange.DAYS_28
        )
        assert len(result.items) == 1
        assert result.items[0].id == second.id


def test_timeline_is_user_scoped_and_empty_for_user_without_records(snapshot_database) -> None:
    _engine, factory = snapshot_database
    with factory() as session:
        owner = _user(session, "timeline-private-owner")
        other = _user(session, "timeline-private-other")
        session.add(
            _timeline_record(
                user_id=owner.id,
                cutoff=date(2026, 7, 18),
                created_at=datetime(2026, 7, 18, 21),
            )
        )
        session.commit()
        result = RunnerStateSnapshotService(
            session,
            clock=lambda: datetime(2026, 7, 19, 12, tzinfo=SHANGHAI),
        ).list_timeline_snapshots(
            user_id=other.id, timeline_range=RunnerStateTimelineRange.DAYS_28
        )
        assert result.total_snapshots == 0
        assert result.days_with_snapshots == 0
        assert result.items == []


def test_timeline_api_defaults_to_28d_and_hides_internal_payload(monkeypatch) -> None:
    current_user = UserAccount(id=806, username="timeline-api", password_hash="x", status="active")
    seen: list[tuple[int, RunnerStateTimelineRange]] = []

    class FakeService:
        def __init__(self, db) -> None:
            pass

        def list_timeline_snapshots(self, *, user_id, timeline_range):
            seen.append((user_id, timeline_range))
            return {
                "range": timeline_range,
                "start_date": date(2026, 6, 22),
                "end_date": date(2026, 7, 19),
                "days_with_snapshots": 0,
                "total_snapshots": 0,
                "items": [],
            }

    monkeypatch.setattr(runner_state_routes, "RunnerStateSnapshotService", FakeService)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    try:
        response = TestClient(app).get("/api/runner-state/snapshots/timeline")
        invalid = TestClient(app).get("/api/runner-state/snapshots/timeline?range=1y")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert seen == [(806, RunnerStateTimelineRange.DAYS_28)]
    assert response.json()["range"] == "28d"
    for hidden in ("snapshot_payload", "payload_hash", "user_id"):
        assert hidden not in response.text
    assert invalid.status_code == 400
