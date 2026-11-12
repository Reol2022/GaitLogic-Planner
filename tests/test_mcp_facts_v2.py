from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from planner_core.config import get_settings
from planner_core.database.models import WorkoutLog
from planner_core.enums import WorkoutStatusNormalized
from server.mcp import facts_v2 as facts
from server.mcp.adapters import McpToolAdapter
from server.mcp.context import McpExecutionContext, McpRequestIdentity
from server.mcp.errors import McpErrorCode, McpSafeError
from server.api.routes.mcp_oauth import _login_page, _requested_scopes
from server.services.auth_service import create_mcp_access_token, decode_mcp_access_token


@pytest.fixture(autouse=True)
def safe_secret(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'synthetic-mcp-v2-signing-secret')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def log(index=1, **kwargs):
    return WorkoutLog(id=index, user_id=101, activity_date=date(2026, 7, 21),
        status_normalized=WorkoutStatusNormalized.completed_normal,
        actual_distance_km=5, workout_type='easy', is_unplanned=True, source_type='manual', **kwargs)


def test_rest_plan_is_not_actual_training_type():
    record = log()
    plan = SimpleNamespace(main_type_normalized='rest', workout_date=record.activity_date)
    item = facts.training_item(record, plan)
    assert item.planned_training_type == 'rest'
    assert item.actual_training_type == 'easy'
    assert item.origin_source == 'UNKNOWN'
    record.workout_type = 'rest'
    assert facts.training_item(record, plan).actual_training_type is None


def test_signed_pagination_is_bound_to_user_range_and_snapshot(monkeypatch):
    rows = [(log(n), None) for n in range(1, 24)]
    monkeypatch.setattr(facts, '_query_logs', lambda *args: rows)
    monkeypatch.setattr(facts, 'local_today', lambda: date(2026, 7, 22))
    db = Mock(); db.scalars.return_value.all.return_value = []
    first = facts.read_training(db, 101, days=30)
    assert len(first.items) == 20 and first.summary.total_sessions == 23
    second = facts.read_training(db, 101, days=30, cursor=first.next_cursor)
    assert len(second.items) == 3 and second.next_cursor is None
    assert second.summary == first.summary and not second.details_complete
    assert not {i.record_ref for i in first.items} & {i.record_ref for i in second.items}
    with pytest.raises(McpSafeError): facts.read_training(db, 202, days=30, cursor=first.next_cursor)
    with pytest.raises(McpSafeError): facts.read_training(db, 101, days=30, cursor=first.next_cursor+'x')
    rows[0][0].actual_distance_km = 6
    with pytest.raises(McpSafeError) as exc: facts.read_training(db, 101, days=30, cursor=first.next_cursor)
    assert exc.value.code == McpErrorCode.CURSOR_STALE


def test_old_scope_cannot_open_recovery_session():
    factory = Mock()
    adapter = McpToolAdapter(McpExecutionContext(identity_provider=lambda: McpRequestIdentity(101), session_factory=factory))
    result = adapter.get_recovery_trend()
    assert result.error.code == McpErrorCode.INSUFFICIENT_PERMISSION
    factory.assert_not_called()


def test_scope_is_explicit_and_survives_signed_token():
    assert _requested_scopes({'scope':'mcp:read arbitrary:write'}) is None
    page = _login_page({'scope':'mcp:read mcp:recovery:read'}).body.decode()
    assert 'name="approve_recovery"' in page
    old = decode_mcp_access_token(create_mcp_access_token(SimpleNamespace(id=101), grant_id='synthetic'))
    assert old['scope'] == 'mcp:read'
    new = decode_mcp_access_token(create_mcp_access_token(SimpleNamespace(id=101), grant_id='synthetic', scopes=['mcp:read','mcp:recovery:read']))
    assert 'mcp:recovery:read' in new['scope'].split()


def test_base_scope_authorization_offers_optional_unchecked_recovery_consent():
    from server.api.routes.mcp_oauth import _consented_scopes
    page = _login_page({'scope': 'mcp:read'}).body.decode()
    checkbox = page.split('name="approve_recovery"', 1)[1].split('>', 1)[0]
    assert 'required' not in checkbox and 'checked' not in checkbox
    assert _consented_scopes({'scope': 'mcp:read', 'approve': 'yes'}) == ['mcp:read']
    assert _consented_scopes({'scope': 'mcp:read', 'approve': 'yes', 'approve_recovery': 'yes'}) == ['mcp:read', 'mcp:recovery:read']
    assert _consented_scopes({'scope': 'mcp:read', 'approve_recovery': 'yes'}) is None
    assert _consented_scopes({'scope': 'mcp:read mcp:recovery:read', 'approve': 'yes'}) is None
    assert _consented_scopes({'scope': 'mcp:read arbitrary:write', 'approve': 'yes', 'approve_recovery': 'yes'}) is None


def test_detail_ownership_is_checked_before_lap_queries():
    db = Mock(); db.scalar.return_value = None
    with pytest.raises(McpSafeError) as exc: facts.read_training_detail(db, 101, 'workout_log:123')
    assert exc.value.code == McpErrorCode.RESOURCE_NOT_FOUND
    params = db.scalar.call_args.args[0].compile().params
    assert 101 in params.values() and 123 in params.values()
    db.scalars.assert_not_called()


def test_empty_recovery_keeps_dates_and_baseline_missing(monkeypatch):
    db = Mock(); db.scalars.return_value.all.return_value = []
    db.execute.return_value.first.return_value = None
    monkeypatch.setattr(facts, 'local_today', lambda: date(2026,7,22))
    result = facts.read_recovery(db, 101)
    assert result.data_status == 'EMPTY' and result.baseline is None
    assert len(result.missing_dates) == 7 and result.daily_records == []
    assert 101 in db.scalars.call_args.args[0].compile().params.values()


def test_conflicting_recorded_rest_is_explicitly_flagged(monkeypatch):
    record = log(); record.workout_type = 'rest'
    monkeypatch.setattr(facts, '_query_logs', lambda *args: [(record, None)])
    monkeypatch.setattr(facts, 'local_today', lambda: date(2026, 7, 22))
    db = Mock(); db.scalars.return_value.all.return_value = []
    result = facts.read_training(db, 101)
    assert result.fact_issues[0].code == 'RECORDED_TYPE_DISTANCE_CONFLICT'
    assert result.items[0].actual_training_type is None
    assert result.summary.total_distance_km == 5


@pytest.mark.parametrize('metric,unit', [('nightly_rmssd', None), ('MS', 'MS')])
def test_hrv_measurement_kind_is_not_fabricated_as_unit(monkeypatch, metric, unit):
    row = SimpleNamespace(checkin_date=date(2026,7,22), source='garmin', hrv_value=50,
        hrv_metric=metric, hrv_source='garmin', sleep_duration_minutes=None,
        resting_heart_rate_bpm=None, sleep_score=None, body_battery_end=None,
        subjective_fatigue=None, sleep_source=None, resting_heart_rate_source=None,
        device_provider='garmin', device_synced_at=None, updated_at=None)
    db = Mock(); db.scalars.return_value.all.return_value = [row]
    db.execute.return_value.first.return_value = None
    monkeypatch.setattr(facts, 'local_today', lambda: date(2026,7,22))
    result = facts.read_recovery(db, 101)
    assert result.daily_records[0].hrv_unit == unit
    assert result.daily_records[0].hrv_metric == metric
