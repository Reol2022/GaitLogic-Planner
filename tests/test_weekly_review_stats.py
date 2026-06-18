from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pymysql
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.base import Base
from planner_core.database.models import (
    PlanAdjustmentDraft,
    PlanAdjustmentItem,
    PlannedWorkout,
    TrainingBlock,
    TrainingCycle,
    UserAccount,
    WeeklyReviewReport,
    WorkoutLog,
)
from planner_core.enums import (
    BlockType,
    PlanAdjustmentAction,
    PlanAdjustmentDraftStatus,
    TrainingStatus,
    WeeklyReviewStatus,
    WorkoutMainTypeNormalized,
    WorkoutStatusNormalized,
)
from server.common.exceptions import BadRequestError, NotFoundError
from server.services.plan_adjustment_apply_service import apply_adjustment_draft
from server.services.plan_adjustment_validation_service import get_adjustment_draft
from server.services.weekly_review_stats_service import build_weekly_review_metrics, local_today
from server.services.ai_plan_service import DeepSeekResult
from server.services import weekly_review_ai_service


@pytest.fixture(scope="module")
def db_session():
    settings = get_settings()
    database = f"gaitlogic_weekly_stats_{uuid4().hex[:10]}"
    try:
        connection = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=3,
        )
    except pymysql.MySQLError as exc:
        pytest.skip(f"MySQL unavailable: {exc}")
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    connection.close()
    engine = create_engine(settings.database_url.replace(settings.mysql_database, database), future=True)
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        cleanup = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
        with cleanup.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cleanup.close()


def add_workout(session, user, cycle, block, day, distance, main_type, status, actual=0, rpe=None, pain=None):
    workout = PlannedWorkout(
        user_id=user.id,
        cycle_id=cycle.id,
        block_id=block.id,
        workout_date=day,
        planned_content=f"{main_type.value} workout",
        planned_distance_km=Decimal(str(distance)),
        main_type_normalized=main_type,
        sort_order=(day - block.start_date).days + 1,
    )
    workout.workout_log = WorkoutLog(
        user_id=user.id,
        status_normalized=status,
        actual_distance_km=Decimal(str(actual)),
        rpe=rpe,
        pain_level=pain,
    )
    session.add(workout)
    return workout


def seed_week(session: Session):
    start = local_today() - timedelta(days=14)
    start -= timedelta(days=start.weekday())
    end = start + timedelta(days=6)
    user = UserAccount(username="weekly-user", password_hash="x", status="active")
    other = UserAccount(username="other-user", password_hash="x", status="active")
    session.add_all([user, other])
    session.flush()
    cycle = TrainingCycle(user_id=user.id, name="Cycle", start_date=start, end_date=end)
    other_cycle = TrainingCycle(user_id=other.id, name="Other", start_date=start, end_date=end)
    session.add_all([cycle, other_cycle])
    session.flush()
    block = TrainingBlock(
        user_id=user.id, cycle_id=cycle.id, block_name="Week", block_type=BlockType.week,
        sort_order=1, start_date=start, end_date=end,
    )
    other_block = TrainingBlock(
        user_id=other.id, cycle_id=other_cycle.id, block_name="Other Week", block_type=BlockType.week,
        sort_order=1, start_date=start, end_date=end,
    )
    session.add_all([block, other_block])
    session.flush()
    rows = [
        (0, 10, WorkoutMainTypeNormalized.easy, WorkoutStatusNormalized.completed_high, 10, 6, 0),
        (1, 0, WorkoutMainTypeNormalized.rest, WorkoutStatusNormalized.rest, 0, None, None),
        (2, 12, WorkoutMainTypeNormalized.tempo, WorkoutStatusNormalized.completed_normal, 11, 8, 2),
        (3, 10, WorkoutMainTypeNormalized.easy, WorkoutStatusNormalized.completed_adjusted, 8, 7, 1),
        (4, 10, WorkoutMainTypeNormalized.interval_speed, WorkoutStatusNormalized.missed, 0, None, None),
        (5, 8, WorkoutMainTypeNormalized.easy, WorkoutStatusNormalized.skipped, 0, None, None),
        (6, 20, WorkoutMainTypeNormalized.long_run, WorkoutStatusNormalized.completed_normal, 18, 7, 0),
    ]
    for offset, distance, kind, status, actual, rpe, pain in rows:
        add_workout(session, user, cycle, block, start + timedelta(days=offset), distance, kind, status, actual, rpe, pain)
    add_workout(
        session, other, other_cycle, other_block, start, 100, WorkoutMainTypeNormalized.easy,
        WorkoutStatusNormalized.completed_normal, 100, 5, 0,
    )
    add_workout(
        session, user, cycle, block, local_today() + timedelta(days=10), 99,
        WorkoutMainTypeNormalized.easy, WorkoutStatusNormalized.completed_normal, 99, 5, 0,
    )
    session.commit()
    return user, cycle, block


def test_weekly_metrics_are_deterministic_user_scoped_and_future_safe(db_session):
    user, cycle, block = seed_week(db_session)
    metrics = build_weekly_review_metrics(db_session, user.id, cycle.id, block.id)
    assert metrics.planned_distance_km == 70
    assert metrics.actual_distance_km == 47
    assert metrics.completion_rate == round(47 / 70, 4)
    assert metrics.planned_workout_days == 6
    assert metrics.completed_workout_days == 4
    assert metrics.completed_high_count == 1
    assert metrics.completed_normal_count == 2
    assert metrics.completed_adjusted_count == 1
    assert metrics.missed_count == 1
    assert metrics.rest_count == 1
    assert metrics.skipped_count == 1
    assert metrics.avg_rpe == 7
    assert metrics.key_workout_avg_rpe == 7.5
    assert metrics.max_pain_level == 2
    assert metrics.planned_type_distance["tempo"] == 12
    assert metrics.actual_type_distance["long_run"] == 18
    assert metrics.recent_7d_distance_km == 47
    assert metrics.valid_log_count == 6
    assert all(item["planned_distance_km"] != 99 for item in metrics.daily_workouts)


def test_zero_denominator_and_no_logs_are_safe(db_session):
    user = UserAccount(username="empty-user", password_hash="x", status="active")
    db_session.add(user)
    db_session.flush()
    start = local_today() - timedelta(days=7)
    cycle = TrainingCycle(user_id=user.id, name="Empty", start_date=start, end_date=start)
    db_session.add(cycle)
    db_session.flush()
    block = TrainingBlock(
        user_id=user.id, cycle_id=cycle.id, block_name="Rest", block_type=BlockType.week,
        sort_order=1, start_date=start, end_date=start,
    )
    db_session.add(block)
    db_session.flush()
    add_workout(
        db_session, user, cycle, block, start, 0, WorkoutMainTypeNormalized.rest,
        WorkoutStatusNormalized.rest, 0,
    )
    db_session.commit()
    metrics = build_weekly_review_metrics(db_session, user.id, cycle.id, block.id)
    assert metrics.completion_rate == 0
    assert metrics.planned_workout_days == 0
    assert metrics.logged_workout_ratio == 0


def create_adjustment_fixture(session: Session, suffix: str, action=PlanAdjustmentAction.reduce):
    user = UserAccount(username=f"adjust-user-{suffix}", password_hash="x", status="active")
    other = UserAccount(username=f"adjust-other-{suffix}", password_hash="x", status="active")
    session.add_all([user, other])
    session.flush()
    start = local_today() - timedelta(days=14)
    cycle = TrainingCycle(user_id=user.id, name=f"Adjust {suffix}", start_date=start, end_date=local_today() + timedelta(days=14))
    session.add(cycle)
    session.flush()
    source = TrainingBlock(user_id=user.id, cycle_id=cycle.id, block_name="Source", block_type=BlockType.week, sort_order=1, start_date=start, end_date=start + timedelta(days=6))
    target = TrainingBlock(user_id=user.id, cycle_id=cycle.id, block_name="Target", block_type=BlockType.week, sort_order=2, start_date=local_today() + timedelta(days=1), end_date=local_today() + timedelta(days=7))
    session.add_all([source, target])
    session.flush()
    workout = PlannedWorkout(
        user_id=user.id, cycle_id=cycle.id, block_id=target.id,
        workout_date=local_today() + timedelta(days=2), planned_content="Tempo 12km",
        planned_distance_km=Decimal("12"), main_type_normalized=WorkoutMainTypeNormalized.tempo,
        target_pace_text="4:00/km", sort_order=1,
    )
    workout.workout_log = WorkoutLog(user_id=user.id, status_normalized=WorkoutStatusNormalized.not_started)
    session.add(workout)
    session.flush()
    report = WeeklyReviewReport(
        user_id=user.id, cycle_id=cycle.id, source_block_id=source.id, target_block_id=target.id,
        week_start_date=source.start_date, week_end_date=source.end_date, version=1,
        status=WeeklyReviewStatus.success, training_status=TrainingStatus.normal,
        metrics_json={"max_pain_level": 0}, source_snapshot_json={"safe": True}, snapshot_hash="a" * 64,
        algorithm_version="test",
    )
    session.add(report)
    session.flush()
    suggested_distance = Decimal("0") if action == PlanAdjustmentAction.rest else Decimal("8")
    suggested_type = "rest" if action == PlanAdjustmentAction.rest else "easy"
    draft = PlanAdjustmentDraft(
        user_id=user.id, review_report_id=report.id, cycle_id=cycle.id,
        source_block_id=source.id, target_block_id=target.id, status=PlanAdjustmentDraftStatus.draft,
        original_week_distance_km=Decimal("12"), suggested_week_distance_km=suggested_distance,
    )
    item = PlanAdjustmentItem(
        draft=draft, planned_workout_id=workout.id, action=action,
        original_content=workout.planned_content, suggested_content="Rest" if action == PlanAdjustmentAction.rest else "Easy 8km",
        original_distance_km=workout.planned_distance_km, suggested_distance_km=suggested_distance,
        original_main_type="tempo", suggested_main_type=suggested_type,
        original_target_pace_text="4:00/km", suggested_target_pace_text=None,
        reason="Test adjustment", is_selected=True,
    )
    session.add(draft)
    session.commit()
    return user, other, report, draft, item, workout


def test_adjustment_is_user_scoped_applies_once_and_preserves_snapshot(db_session):
    user, other, report, draft, item, workout = create_adjustment_fixture(db_session, uuid4().hex[:6])
    with pytest.raises(NotFoundError):
        get_adjustment_draft(db_session, draft.id, other.id)
    result = apply_adjustment_draft(db_session, user.id, draft.id, [item.id])
    assert result.applied_item_ids == [item.id]
    db_session.refresh(workout)
    db_session.refresh(report)
    assert float(workout.planned_distance_km) == 8
    assert workout.main_type_normalized == WorkoutMainTypeNormalized.easy
    assert report.source_snapshot_json == {"safe": True}
    with pytest.raises(BadRequestError):
        apply_adjustment_draft(db_session, user.id, draft.id, [item.id])


def test_rest_adjustment_sets_distance_to_zero(db_session):
    user, _, _, draft, item, workout = create_adjustment_fixture(
        db_session, uuid4().hex[:6], PlanAdjustmentAction.rest
    )
    apply_adjustment_draft(db_session, user.id, draft.id, [item.id])
    db_session.refresh(workout)
    assert float(workout.planned_distance_km) == 0
    assert workout.main_type_normalized == WorkoutMainTypeNormalized.rest


def test_weekly_review_generation_uses_mock_and_reuses_same_snapshot(db_session, monkeypatch):
    user, _, _, draft, _, _ = create_adjustment_fixture(db_session, uuid4().hex[:6])
    # Remove the hand-built draft/report so the generation service can create its own version.
    source_id = draft.source_block_id
    target_id = draft.target_block_id
    cycle_id = draft.cycle_id
    db_session.delete(draft.review_report)
    db_session.commit()
    payload = {
        "summary": "记录较少，本次仅做保守总结。",
        "positive_points": ["已建立下一周计划"],
        "attention_points": ["继续填写训练日志"],
        "training_status": "insufficient_data",
        "status_explanation": "有效日志不足。",
        "next_week_strategy": "保持保守，不主动加量。",
        "adjustments": [
            {
                "planned_workout_id": db_session.query(PlannedWorkout).filter_by(block_id=target_id).one().id,
                "action": "reduce",
                "suggested_content": "Easy 8km",
                "suggested_distance_km": 8,
                "suggested_main_type": "easy",
                "suggested_target_pace_text": None,
                "reason": "数据不足时保持保守",
            }
        ],
        "risk_notes": ["本结果不是医疗诊断"],
    }
    monkeypatch.setattr(
        weekly_review_ai_service,
        "call_deepseek",
        lambda *args, **kwargs: DeepSeekResult(content=__import__("json").dumps(payload), input_tokens=10, output_tokens=20, total_tokens=30),
    )
    first = weekly_review_ai_service.generate_weekly_review(
        db_session, user.id, cycle_id, source_id, target_id
    )
    second = weekly_review_ai_service.generate_weekly_review(
        db_session, user.id, cycle_id, source_id, target_id
    )
    assert first.report.status.value == "success"
    assert first.adjustment_draft is not None
    assert second.report.id == first.report.id
