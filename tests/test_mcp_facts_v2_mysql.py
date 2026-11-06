"""Opt-in real MySQL acceptance using only an explicitly isolated test schema."""
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from planner_core.database.models import Base, DailyRecoveryCheckin, UserAccount, WorkoutLog
from planner_core.enums import WorkoutStatusNormalized
from server.mcp.facts_v2 import read_recovery, read_training, read_training_detail
from server.mcp.errors import McpSafeError
from server.services.weekly_review_stats_service import local_today


def test_mysql_facts_paging_ownership_and_read_only(monkeypatch):
    raw = os.getenv('GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL')
    if not raw: pytest.skip('Explicit isolated MySQL URL required')
    url = make_url(raw)
    if url.get_backend_name() != 'mysql' or url.host not in {'127.0.0.1','localhost'} or not (url.database or '').startswith('gaitlogic_test_'):
        pytest.fail('Refusing non-local or non-test schema')
    monkeypatch.setenv('JWT_SECRET_KEY', 'synthetic-mcp-v2-integration-secret')
    from planner_core.config import get_settings
    get_settings.cache_clear()
    engine = create_engine(url)
    # Only the isolated schema above may be initialized.
    Base.metadata.create_all(engine)
    ids = []
    today = local_today()
    try:
        with Session(engine) as db:
            users = [UserAccount(username='synthetic-v2-'+uuid4().hex[:14], password_hash='not-a-login', status='active') for _ in range(2)]
            db.add_all(users); db.flush(); ids = [u.id for u in users]
            logs = [WorkoutLog(user_id=ids[0], activity_date=today-timedelta(days=n), workout_type='easy', is_unplanned=True, status_normalized=WorkoutStatusNormalized.completed_normal, source_type='manual', actual_distance_km=5, actual_duration_seconds=1800) for n in range(25)]
            db.add_all(logs)
            db.add(DailyRecoveryCheckin(user_id=ids[0], checkin_date=today, hrv_value=60, hrv_metric='MS', hrv_source='manual'))
            db.commit(); record_ref = f'workout_log:{logs[0].id}'
        reads = []
        def ensure_read(_conn, _cursor, statement, *_args):
            verb = statement.lstrip().split()[0].upper()
            reads.append(verb)
            if verb in {'INSERT','UPDATE','DELETE','ALTER','CREATE','DROP'}: raise AssertionError('Read tool attempted mutation')
        event.listen(engine, 'before_cursor_execute', ensure_read)
        try:
            with Session(engine) as db:
                first = read_training(db, ids[0], days=30)
                second = read_training(db, ids[0], days=30, cursor=first.next_cursor)
                assert len(first.items) == 20 and len(second.items) == 5
                assert first.summary.total_distance_km == second.summary.total_distance_km == 125
                assert read_training(db, ids[1], days=30).items == []
                detail = read_training_detail(db, ids[0], record_ref)
                assert not detail.segments_available and not detail.segments
                with pytest.raises(McpSafeError): read_training_detail(db, ids[1], record_ref)
                assert len(read_recovery(db, ids[0]).daily_records) == 1
                assert read_recovery(db, ids[1]).daily_records == []
            assert reads
        finally: event.remove(engine, 'before_cursor_execute', ensure_read)
    finally:
        with Session(engine) as db:
            if ids:
                db.execute(delete(WorkoutLog).where(WorkoutLog.user_id.in_(ids)))
                db.execute(delete(DailyRecoveryCheckin).where(DailyRecoveryCheckin.user_id.in_(ids)))
                db.execute(delete(UserAccount).where(UserAccount.id.in_(ids)))
                db.commit()
        engine.dispose(); get_settings.cache_clear()
