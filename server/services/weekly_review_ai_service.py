from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import (
    AIPlanJob,
    PlanAdjustmentDraft,
    PlanAdjustmentItem,
    PlannedWorkout,
    TrainingBlock,
    WeeklyReviewReport,
)
from planner_core.enums import (
    AIPlanJobStatus,
    PlanAdjustmentDraftStatus,
    TrainingStatus,
    WeeklyReviewStatus,
)
from server.common.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError, TooManyRequestsError
from server.schemas.weekly_review import (
    PlanAdjustmentDraftRead,
    PlanAdjustmentItemRead,
    TrainingStatusResult,
    WeeklyReviewAIOutput,
    WeeklyReviewDetailResponse,
    WeeklyReviewListResponse,
    WeeklyReviewReportRead,
)
from server.services.admin_ai_settings_service import get_effective_ai_settings
from server.services.ai_coach_preference_service import get_or_create_preference, preference_to_prompt_dict
from server.services.ai_plan_service import (
    call_deepseek,
    check_ai_plan_quota,
    load_ai_json,
    normalize_ai_generation_exception,
    prompt_hash_for_input,
    save_job,
)
from server.services.plan_adjustment_validation_service import validate_ai_adjustments
from server.services.readiness_assessment_service import evaluate_and_save_readiness
from server.services.training_block_service import get_training_block
from server.services.training_status_service import evaluate_training_status
from server.services.weekly_review_prompt import (
    WEEKLY_REVIEW_PROMPT_VERSION,
    build_weekly_review_user_prompt,
    get_weekly_review_system_prompt,
)
from server.services.weekly_review_stats_service import build_weekly_review_metrics, save_block_review_metrics
from server.services.weekly_review_stats_service import local_today

ALGORITHM_VERSION = "weekly-review-rules-v1"


def _target_block(db: Session, user_id: int, cycle_id: int, source: TrainingBlock, target_id: int | None):
    if target_id is not None:
        target = get_training_block(db, target_id, user_id)
        if target.cycle_id != cycle_id or target.id == source.id:
            raise BadRequestError("Target block must be a different block in the selected cycle.")
        return target
    return db.scalar(
        select(TrainingBlock)
        .where(
            TrainingBlock.user_id == user_id,
            TrainingBlock.cycle_id == cycle_id,
            TrainingBlock.sort_order > source.sort_order,
        )
        .order_by(TrainingBlock.sort_order, TrainingBlock.id)
        .limit(1)
    )


def _target_workouts(db: Session, user_id: int, target_block_id: int | None) -> list[PlannedWorkout]:
    if target_block_id is None:
        return []
    return list(
        db.scalars(
            select(PlannedWorkout)
            .options(selectinload(PlannedWorkout.workout_log))
            .where(PlannedWorkout.user_id == user_id, PlannedWorkout.block_id == target_block_id)
            .order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order, PlannedWorkout.id)
        )
    )


def _subjective_notes(metrics, workouts: list[PlannedWorkout]) -> list[dict]:
    source_ids = {item["planned_workout_id"] for item in metrics.daily_workouts}
    return [
        {
            "planned_workout_id": item.id,
            "date": item.workout_date.isoformat() if item.workout_date else None,
            "leg_feeling": item.workout_log.leg_feeling,
            "pain_location": item.workout_log.pain_location,
            "pain_level": item.workout_log.pain_level,
            "review_note": item.workout_log.review_note,
            "alert_message": item.workout_log.alert_message,
        }
        for item in workouts
        if item.id in source_ids
        and item.workout_log
        and any(
            (
                item.workout_log.leg_feeling,
                item.workout_log.pain_location,
                item.workout_log.review_note,
                item.workout_log.alert_message,
                item.workout_log.pain_level,
            )
        )
    ]


def build_source_snapshot(db: Session, user_id: int, cycle_id: int, source_block_id: int, target_block_id: int | None):
    metrics = build_weekly_review_metrics(db, user_id, cycle_id, source_block_id)
    status_result = evaluate_training_status(metrics)
    readiness = evaluate_and_save_readiness(db, user_id, min(metrics.week_end_date, local_today()))
    status_result = TrainingStatusResult(
        status=readiness.status,
        reasons=list(readiness.reasons_json or []),
        signals=[],
        missing_data=list(readiness.missing_data_json or []),
    )
    metrics.readiness_status = readiness.status
    metrics.readiness_data_quality = readiness.data_quality.value
    metrics.rolling_7d_srpe_load_au = readiness.metrics_json.get("rolling_7d_srpe_load_au")
    metrics.baseline_28d_weekly_srpe_load_au = readiness.metrics_json.get("baseline_28d_weekly_srpe_load_au")
    metrics.recent_to_baseline_load_ratio = readiness.metrics_json.get("recent_to_baseline_load_ratio")
    metrics.recovery_checkin_coverage_ratio = readiness.metrics_json.get("recovery_checkin_coverage_ratio")
    source = get_training_block(db, source_block_id, user_id)
    target = _target_block(db, user_id, cycle_id, source, target_block_id)
    source_workouts = list(
        db.scalars(
            select(PlannedWorkout)
            .options(selectinload(PlannedWorkout.workout_log))
            .where(PlannedWorkout.user_id == user_id, PlannedWorkout.block_id == source_block_id)
        )
    )
    target_workouts = _target_workouts(db, user_id, target.id if target else None)
    preference = preference_to_prompt_dict(get_or_create_preference(db, user_id))
    snapshot = {
        "metrics": metrics.model_dump(mode="json"),
        "rule_result": status_result.model_dump(mode="json"),
        "source_block": {"id": source.id, "name": source.block_name, "focus": source.focus},
        "subjective_notes": _subjective_notes(metrics, source_workouts),
        "target_block": (
            {"id": target.id, "name": target.block_name, "focus": target.focus} if target else None
        ),
        "next_week_plan": [
            {
                "planned_workout_id": item.id,
                "date": item.workout_date.isoformat() if item.workout_date else None,
                "planned_content": item.planned_content,
                "planned_distance_km": float(item.planned_distance_km or 0),
                "main_type": item.main_type_normalized.value,
                "target_pace_text": item.target_pace_text,
            }
            for item in target_workouts
        ],
        "training_preference": preference,
        "algorithm_version": ALGORITHM_VERSION,
    }
    return metrics, status_result, source, target, target_workouts, snapshot


def snapshot_hash(snapshot: dict) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _report_version(db: Session, user_id: int, source_block_id: int) -> int:
    value = db.scalar(
        select(func.max(WeeklyReviewReport.version)).where(
            WeeklyReviewReport.user_id == user_id,
            WeeklyReviewReport.source_block_id == source_block_id,
        )
    )
    return int(value or 0) + 1


def _cached_report(db: Session, user_id: int, source_block_id: int, target_block_id: int | None, digest: str):
    return db.scalar(
        select(WeeklyReviewReport)
        .where(
            WeeklyReviewReport.user_id == user_id,
            WeeklyReviewReport.source_block_id == source_block_id,
            WeeklyReviewReport.target_block_id == target_block_id,
            WeeklyReviewReport.snapshot_hash == digest,
            WeeklyReviewReport.status == WeeklyReviewStatus.success,
        )
        .order_by(WeeklyReviewReport.version.desc())
        .limit(1)
    )


def _create_draft(
    db: Session,
    report: WeeklyReviewReport,
    output: WeeklyReviewAIOutput,
    target_workouts: list[PlannedWorkout],
) -> PlanAdjustmentDraft | None:
    if report.target_block_id is None:
        return None
    by_id = {item.id: item for item in target_workouts}
    original_total = sum(float(item.planned_distance_km or 0) for item in target_workouts)
    suggested_by_id = {item.planned_workout_id: item for item in output.adjustments}
    suggested_total = sum(
        suggested_by_id[item.id].suggested_distance_km if item.id in suggested_by_id else float(item.planned_distance_km or 0)
        for item in target_workouts
    )
    draft = PlanAdjustmentDraft(
        user_id=report.user_id,
        review_report_id=report.id,
        cycle_id=report.cycle_id,
        source_block_id=report.source_block_id,
        target_block_id=report.target_block_id,
        status=PlanAdjustmentDraftStatus.draft,
        summary=output.next_week_strategy,
        original_week_distance_km=Decimal(str(original_total)),
        suggested_week_distance_km=Decimal(str(suggested_total)),
    )
    for adjustment in output.adjustments:
        workout = by_id[adjustment.planned_workout_id]
        draft.items.append(
            PlanAdjustmentItem(
                planned_workout_id=workout.id,
                action=adjustment.action,
                original_content=workout.planned_content,
                suggested_content=adjustment.suggested_content,
                original_distance_km=workout.planned_distance_km,
                suggested_distance_km=Decimal(str(adjustment.suggested_distance_km)),
                original_main_type=workout.main_type_normalized.value,
                suggested_main_type=adjustment.suggested_main_type.value,
                original_target_pace_text=workout.target_pace_text,
                suggested_target_pace_text=adjustment.suggested_target_pace_text,
                reason=adjustment.reason,
                is_selected=adjustment.action.value != "keep",
            )
        )
    db.add(draft)
    return draft


def generate_weekly_review(
    db: Session, user_id: int, cycle_id: int, source_block_id: int, target_block_id: int | None
) -> WeeklyReviewDetailResponse:
    metrics, status_result, source, target, target_workouts, snapshot = build_source_snapshot(
        db, user_id, cycle_id, source_block_id, target_block_id
    )
    digest = snapshot_hash(snapshot)
    cached = _cached_report(db, user_id, source_block_id, target.id if target else None, digest)
    if cached:
        return get_weekly_review_detail(db, user_id, cached.id)
    if target is None:
        raise BadRequestError("No next training block is available for adjustment.")

    runtime = get_effective_ai_settings(db)
    quota = check_ai_plan_quota(db, user_id)
    job_input = {
        "usage_type": "weekly_review",
        "snapshot_hash": digest,
        "cycle_id": cycle_id,
        "source_block_id": source_block_id,
        "target_block_id": target.id,
    }
    job = save_job(db, user_id, runtime.ai_model, prompt_hash_for_input(job_input), job_input)
    report = WeeklyReviewReport(
        user_id=user_id,
        cycle_id=cycle_id,
        source_block_id=source_block_id,
        target_block_id=target.id,
        week_start_date=metrics.week_start_date,
        week_end_date=metrics.week_end_date,
        version=_report_version(db, user_id, source_block_id),
        status=WeeklyReviewStatus.generating,
        training_status=status_result.status,
        metrics_json=metrics.model_dump(mode="json"),
        rule_reasons_json=status_result.reasons,
        missing_data_json=status_result.missing_data,
        source_snapshot_json=snapshot,
        snapshot_hash=digest,
        algorithm_version=ALGORITHM_VERSION,
        prompt_version=WEEKLY_REVIEW_PROMPT_VERSION,
        model_name=runtime.ai_model,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    try:
        result = call_deepseek(
            get_weekly_review_system_prompt(), build_weekly_review_user_prompt(snapshot), 1, runtime
        )
        try:
            output = WeeklyReviewAIOutput.model_validate(load_ai_json(result.content))
        except ValidationError as exc:
            raise BadRequestError("AI weekly review output failed schema validation.") from exc
        validate_ai_adjustments(
            db, user_id, target.id, output, status_result.status, metrics.max_pain_level
        )
        report.summary = output.summary
        report.positive_points_json = output.positive_points
        report.attention_points_json = output.attention_points
        report.next_week_strategy = output.next_week_strategy
        report.risk_notes_json = output.risk_notes
        report.status = WeeklyReviewStatus.success
        report.generated_at = datetime.utcnow()
        job.output_json = output.model_dump(mode="json")
        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.total_tokens = result.total_tokens
        job.status = AIPlanJobStatus.success
        job.finished_at = datetime.utcnow()
        quota.used_count += 1
        quota.last_generated_at = datetime.utcnow()
        save_block_review_metrics(db, user_id, source_block_id, metrics)
        _create_draft(db, report, output, target_workouts)
        db.commit()
        return get_weekly_review_detail(db, user_id, report.id)
    except Exception as exc:
        db.rollback()
        report = db.get(WeeklyReviewReport, report.id)
        job = db.get(AIPlanJob, job.id)
        if report:
            report.status = WeeklyReviewStatus.failed
            report.error_message = f"Weekly review generation failed: {type(exc).__name__}"
        if job:
            job.status = AIPlanJobStatus.failed
            job.error_message = f"Weekly review generation failed: {type(exc).__name__}"
            job.finished_at = datetime.utcnow()
        db.commit()
        if isinstance(exc, (BadRequestError, TooManyRequestsError, ServiceUnavailableError)):
            raise
        raise normalize_ai_generation_exception(exc) from exc


def _draft_read(draft: PlanAdjustmentDraft | None) -> PlanAdjustmentDraftRead | None:
    if draft is None:
        return None
    items = [
        PlanAdjustmentItemRead(
            id=item.id,
            draft_id=item.draft_id,
            planned_workout_id=item.planned_workout_id,
            workout_date=item.planned_workout.workout_date,
            action=item.action,
            original_content=item.original_content,
            suggested_content=item.suggested_content,
            original_distance_km=float(item.original_distance_km) if item.original_distance_km is not None else None,
            suggested_distance_km=float(item.suggested_distance_km) if item.suggested_distance_km is not None else None,
            original_main_type=item.original_main_type,
            suggested_main_type=item.suggested_main_type,
            original_target_pace_text=item.original_target_pace_text,
            suggested_target_pace_text=item.suggested_target_pace_text,
            reason=item.reason,
            is_selected=item.is_selected,
            is_applied=item.is_applied,
            applied_at=item.applied_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in draft.items
    ]
    return PlanAdjustmentDraftRead(
        id=draft.id,
        review_report_id=draft.review_report_id,
        cycle_id=draft.cycle_id,
        source_block_id=draft.source_block_id,
        target_block_id=draft.target_block_id,
        status=draft.status,
        summary=draft.summary,
        original_week_distance_km=float(draft.original_week_distance_km or 0),
        suggested_week_distance_km=float(draft.suggested_week_distance_km or 0),
        applied_at=draft.applied_at,
        rejected_at=draft.rejected_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        items=items,
    )


def get_weekly_review_detail(db: Session, user_id: int, review_id: int) -> WeeklyReviewDetailResponse:
    report = db.scalar(
        select(WeeklyReviewReport)
        .options(
            selectinload(WeeklyReviewReport.adjustment_draft)
            .selectinload(PlanAdjustmentDraft.items)
            .selectinload(PlanAdjustmentItem.planned_workout)
        )
        .where(WeeklyReviewReport.id == review_id, WeeklyReviewReport.user_id == user_id)
    )
    if report is None:
        raise NotFoundError("Weekly review report not found.")
    if report.adjustment_draft:
        report.adjustment_draft.items.sort(
            key=lambda item: (item.planned_workout.workout_date or datetime.max.date(), item.id)
        )
    return WeeklyReviewDetailResponse(
        report=WeeklyReviewReportRead.model_validate(report),
        adjustment_draft=_draft_read(report.adjustment_draft),
    )


def list_weekly_reviews(
    db: Session, user_id: int, cycle_id: int | None, page: int, page_size: int
) -> WeeklyReviewListResponse:
    filters = [WeeklyReviewReport.user_id == user_id]
    if cycle_id is not None:
        filters.append(WeeklyReviewReport.cycle_id == cycle_id)
    total = int(db.scalar(select(func.count()).select_from(WeeklyReviewReport).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(WeeklyReviewReport)
            .where(*filters)
            .order_by(WeeklyReviewReport.created_at.desc(), WeeklyReviewReport.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return WeeklyReviewListResponse(
        items=[WeeklyReviewReportRead.model_validate(item) for item in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
