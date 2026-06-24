from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from planner_core.database.models import FeatureAccess, TrainingReadinessAssessment, UsageEvent
from planner_core.enums import FeatureKey, UsageEventName
from server.common.exceptions import BadRequestError
from server.schemas.usage_event import ProductMetricsRead, UsageEventCreate

SENSITIVE_METADATA_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "prompt",
    "content",
    "review_note",
    "main_session_data",
    "injury",
    "pain",
    "summary",
    "risk_notes",
    "training_log",
}


def assert_safe_metadata(metadata: dict[str, Any] | None) -> None:
    if not metadata:
        return
    for key in metadata:
        lowered = str(key).lower()
        if lowered in SENSITIVE_METADATA_KEYS or any(
            part in lowered
            for part in ("password", "token", "secret", "api_key", "prompt", "injury", "pain", "review_text")
        ):
            raise BadRequestError("Usage event metadata contains sensitive fields.")


def record_usage_event(db: Session, user_id: int | None, payload: UsageEventCreate) -> UsageEvent:
    metadata = payload.metadata_json or None
    assert_safe_metadata(metadata)
    event = UsageEvent(
        user_id=user_id,
        event_name=payload.event_name,
        page_path=payload.page_path,
        metadata_json=metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _range_filter(stmt, start_date: date | None, end_date: date | None):
    if start_date:
        stmt = stmt.where(UsageEvent.occurred_at >= datetime.combine(start_date, time.min))
    if end_date:
        stmt = stmt.where(UsageEvent.occurred_at <= datetime.combine(end_date, time.max))
    return stmt


def count_distinct_users(
    db: Session,
    event_name: UsageEventName,
    start_date: date | None,
    end_date: date | None,
) -> int:
    stmt = select(func.count(distinct(UsageEvent.user_id))).where(
        UsageEvent.event_name == event_name,
        UsageEvent.user_id.is_not(None),
    )
    stmt = _range_filter(stmt, start_date, end_date)
    return int(db.scalar(stmt) or 0)


def _count_allowlisted_training_readiness_users(db: Session) -> int:
    now = datetime.utcnow()
    return int(
        db.scalar(
            select(func.count(distinct(FeatureAccess.user_id))).where(
                FeatureAccess.feature_key == FeatureKey.training_readiness,
                FeatureAccess.enabled.is_(True),
                (FeatureAccess.expires_at.is_(None) | (FeatureAccess.expires_at > now)),
            )
        )
        or 0
    )


def _readiness_distribution(db: Session, field, start_date: date | None, end_date: date | None) -> dict[str, int]:
    stmt = select(field, func.count()).select_from(TrainingReadinessAssessment).group_by(field)
    if start_date:
        stmt = stmt.where(TrainingReadinessAssessment.generated_at >= datetime.combine(start_date, time.min))
    if end_date:
        stmt = stmt.where(TrainingReadinessAssessment.generated_at <= datetime.combine(end_date, time.max))
    return {str(key.value if hasattr(key, "value") else key): int(count) for key, count in db.execute(stmt).all()}


def _readiness_assessment_count(db: Session, start_date: date | None, end_date: date | None) -> int:
    stmt = select(func.count()).select_from(TrainingReadinessAssessment)
    if start_date:
        stmt = stmt.where(TrainingReadinessAssessment.generated_at >= datetime.combine(start_date, time.min))
    if end_date:
        stmt = stmt.where(TrainingReadinessAssessment.generated_at <= datetime.combine(end_date, time.max))
    return int(db.scalar(stmt) or 0)


def get_product_metrics(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ProductMetricsRead:
    onboarding = count_distinct_users(db, UsageEventName.onboarding_viewed, start_date, end_date)
    generated = count_distinct_users(db, UsageEventName.ai_plan_generate_succeeded, start_date, end_date)
    applied = count_distinct_users(db, UsageEventName.ai_plan_applied, start_date, end_date)
    today = count_distinct_users(db, UsageEventName.today_viewed, start_date, end_date)
    logged = count_distinct_users(db, UsageEventName.workout_log_saved, start_date, end_date)
    recovery_saved = count_distinct_users(db, UsageEventName.recovery_checkin_saved, start_date, end_date)
    readiness_viewed = count_distinct_users(db, UsageEventName.readiness_detail_viewed, start_date, end_date)
    readiness_recalculated = count_distinct_users(db, UsageEventName.readiness_recalculated, start_date, end_date)
    reduce_load_viewed = count_distinct_users(db, UsageEventName.reduce_load_suggestion_viewed, start_date, end_date)
    return ProductMetricsRead(
        start_date=start_date,
        end_date=end_date,
        onboarding_viewed_users=onboarding,
        ai_plan_generate_succeeded_users=generated,
        ai_plan_applied_users=applied,
        today_viewed_users=today,
        workout_log_saved_users=logged,
        generate_to_apply_rate=round(applied / generated, 4) if generated else 0,
        apply_to_first_checkin_rate=round(logged / applied, 4) if applied else 0,
        training_readiness_allowlisted_users=_count_allowlisted_training_readiness_users(db),
        recovery_checkin_saved_users=recovery_saved,
        readiness_detail_viewed_users=readiness_viewed,
        readiness_recalculated_users=readiness_recalculated,
        reduce_load_suggestion_viewed_users=reduce_load_viewed,
        readiness_assessment_success_count=_readiness_assessment_count(db, start_date, end_date),
        readiness_status_distribution=_readiness_distribution(
            db, TrainingReadinessAssessment.status, start_date, end_date
        ),
        readiness_data_quality_distribution=_readiness_distribution(
            db, TrainingReadinessAssessment.data_quality, start_date, end_date
        ),
    )
