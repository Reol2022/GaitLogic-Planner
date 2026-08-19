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
from server.common.exceptions import AppError, BadRequestError, NotFoundError, ServiceUnavailableError, TooManyRequestsError
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
from server.services.weekly_review_stats_service import (
    COMPLETED_STATUSES,
    build_weekly_review_metrics,
    save_block_review_metrics,
)
from server.services.weekly_review_stats_service import local_today
from planner_core.config import get_settings
from server.model_tasks import ModelTaskType, task_model_profile
from server.services.provider_reasoning_service import persist_reasoning
from server.structured_task_provider import StructuredTaskProvider, StructuredTaskProviderError
from server.weekly_review_graph.schemas import PlanDesignAnalysis, WeeklyReviewAnalysis
from server.provider_reliability import ProviderFailureCategory

ALGORITHM_VERSION = "weekly-review-rules-v1"


def _provider_error(exc: StructuredTaskProviderError) -> AppError:
    if exc.category == ProviderFailureCategory.PROVIDER_OUTPUT_TRUNCATED:
        return BadRequestError("模型输出达到长度限制，最终正文未完整生成。")
    if exc.category == ProviderFailureCategory.PROVIDER_EMPTY_CONTENT:
        return BadRequestError("模型没有返回可用的最终正文。")
    if exc.category == ProviderFailureCategory.PROVIDER_INVALID_JSON:
        return BadRequestError("模型返回的正文不是合法 JSON。")
    if exc.category == ProviderFailureCategory.PROVIDER_SCHEMA_ERROR:
        return BadRequestError("模型返回结果未通过结构校验。")
    if exc.category == ProviderFailureCategory.PROVIDER_TIMEOUT:
        return ServiceUnavailableError("AI 周复盘模型请求超时，请稍后重试。")
    if exc.category == ProviderFailureCategory.PROVIDER_RATE_LIMIT:
        return TooManyRequestsError("AI 服务当前请求较多，请稍后重试。")
    if exc.category == ProviderFailureCategory.PROVIDER_AUTH_ERROR:
        return ServiceUnavailableError("AI 服务认证配置无效，请联系管理员检查 Provider 配置。")
    if exc.category in {
        ProviderFailureCategory.PROVIDER_CONNECTION_ERROR,
        ProviderFailureCategory.PROVIDER_SERVER_ERROR,
    }:
        return ServiceUnavailableError("AI Provider 暂时不可用，请稍后重试。")
    if exc.category == ProviderFailureCategory.PROVIDER_BAD_REQUEST:
        return BadRequestError("AI Provider 拒绝了周复盘请求，请联系管理员检查模型配置。")
    return BadRequestError("AI 周复盘服务暂时不可用。")


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


def _is_adjustable_target_workout(item: PlannedWorkout) -> bool:
    if item.is_locked:
        return False
    if item.workout_date is not None and item.workout_date < local_today():
        return False
    return not (
        item.workout_log
        and item.workout_log.status_normalized in COMPLETED_STATUSES
    )


def _filter_adjustable_candidates(candidates, next_week_plan: list[dict]):
    adjustable_ids = {item["planned_workout_id"] for item in next_week_plan}
    accepted = [item for item in candidates if item.plan_id in adjustable_ids]
    warnings = (
        ["模型返回了不可调整的历史、已完成、锁定或越界课表，相关建议已被安全忽略。"]
        if len(accepted) != len(candidates)
        else []
    )
    return accepted, warnings


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
    adjustable_target_workouts = [
        item for item in target_workouts if _is_adjustable_target_workout(item)
    ]
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
            for item in adjustable_target_workouts
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
            WeeklyReviewReport.algorithm_version == ALGORITHM_VERSION,
            WeeklyReviewReport.prompt_version == WEEKLY_REVIEW_PROMPT_VERSION,
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
    if report.target_block_id is None or not output.adjustments:
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
    db: Session,
    user_id: int,
    cycle_id: int,
    source_block_id: int,
    target_block_id: int | None,
    force_regenerate: bool = False,
) -> WeeklyReviewDetailResponse:
    metrics, status_result, source, target, target_workouts, snapshot = build_source_snapshot(
        db, user_id, cycle_id, source_block_id, target_block_id
    )
    digest = snapshot_hash(snapshot)
    cached = _cached_report(db, user_id, source_block_id, target.id if target else None, digest)
    if cached and not force_regenerate:
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
        provider_settings = get_settings().model_copy(
            update={
                "ai_api_key": runtime.ai_api_key,
                "deepseek_base_url": runtime.ai_base_url,
                "deepseek_model": runtime.ai_model,
                "deepseek_timeout_seconds": runtime.ai_timeout_seconds,
            }
        )
        provider = StructuredTaskProvider(provider_settings)
        weekly_profile = task_model_profile(provider_settings, ModelTaskType.WEEKLY_REVIEW_ANALYSIS)
        weekly_result = provider.generate(
            profile=weekly_profile,
            schema=WeeklyReviewAnalysis,
            system_prompt=(
                "Analyze the supplied deterministic weekly running snapshot. Do not design or modify the "
                "next-week plan in this task. Treat rule results and missing data as authoritative. Return JSON only."
            ),
            input_payload={"snapshot": snapshot},
        )
        analysis = WeeklyReviewAnalysis.model_validate(weekly_result.value)
        persist_reasoning(
            db,
            user_id=user_id,
            provider="openai-compatible",
            profile=weekly_profile,
            result=weekly_result,
            related_record_type="weekly_review_report",
            related_record_id=report.id,
        )
        plan_profile = task_model_profile(provider_settings, ModelTaskType.PLAN_DESIGN)
        plan_result = provider.generate(
            profile=plan_profile,
            schema=PlanDesignAnalysis,
            system_prompt=(
                "Design conservative candidate adjustments for the supplied existing next-week plan. Use only "
                "supplied workout IDs and deterministic rule codes. Partial or blocked recovery data cannot justify "
                "an increase. Return JSON only; the server will materialize and validate changes."
            ),
            input_payload={
                "weekly_review_analysis": analysis.model_dump(mode="json"),
                "next_week_plan": snapshot["next_week_plan"],
                "rule_result": snapshot["rule_result"],
                "training_preference": snapshot["training_preference"],
            },
        )
        design = PlanDesignAnalysis.model_validate(plan_result.value)
        persist_reasoning(
            db,
            user_id=user_id,
            provider="openai-compatible",
            profile=plan_profile,
            result=plan_result,
            related_record_type="weekly_review_report",
            related_record_id=report.id,
        )
        accepted_adjustments, materialize_warnings = _filter_adjustable_candidates(
            design.candidate_adjustments,
            snapshot["next_week_plan"],
        )
        output = WeeklyReviewAIOutput.model_validate(
            {
                "summary": analysis.overall_assessment,
                "positive_points": analysis.positive_signals,
                "attention_points": analysis.risk_signals,
                "training_status": status_result.status,
                "status_explanation": analysis.recovery_assessment,
                "next_week_strategy": design.reason_summary,
                "adjustments": [
                    {
                        "planned_workout_id": item.plan_id,
                        "action": item.action,
                        "suggested_content": item.after.content,
                        "suggested_distance_km": item.after.distance_km or 0,
                        "suggested_main_type": item.after.main_type,
                        "suggested_target_pace_text": item.after.target_pace_text,
                        "reason": item.reason,
                    }
                    for item in accepted_adjustments
                ],
                "risk_notes": list(
                    dict.fromkeys(
                        [*analysis.warnings, *design.warnings, *materialize_warnings]
                    )
                ),
            }
        )
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
        job.input_tokens = (weekly_result.prompt_tokens or 0) + (plan_result.prompt_tokens or 0)
        job.output_tokens = (weekly_result.completion_tokens or 0) + (plan_result.completion_tokens or 0)
        job.total_tokens = job.input_tokens + job.output_tokens
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
            failure_name = (
                exc.category.value if isinstance(exc, StructuredTaskProviderError) else type(exc).__name__
            )
            report.error_message = f"Weekly review generation failed: {failure_name}"
        if job:
            job.status = AIPlanJobStatus.failed
            failure_name = (
                exc.category.value if isinstance(exc, StructuredTaskProviderError) else type(exc).__name__
            )
            job.error_message = f"Weekly review generation failed: {failure_name}"
            job.finished_at = datetime.utcnow()
        db.commit()
        if isinstance(exc, StructuredTaskProviderError):
            raise _provider_error(exc) from exc
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
