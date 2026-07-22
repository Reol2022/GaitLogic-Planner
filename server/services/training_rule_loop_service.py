from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner_core.database.models import PlannedWorkout, TrainingAdjustmentDraft, TrainingRuleEvaluation
from planner_core.enums import WorkoutMainTypeNormalized
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.training_rule_loop import RuleLoopEvaluationResponse, RuleLoopSummary
from server.schemas.training_rules import TrainingRuleEvaluateResponse
from server.services import training_rule_service
from server.services.training_facts.common import SOURCE_VERSION, decimal_float, enum_value, hash_facts, is_high_intensity
from server.services.training_facts.daily_facts import build_daily_facts
from server.services.training_facts.plan_facts import build_ai_draft_plan_facts, build_cycle_plan_facts, build_plan_import_facts
from server.services.training_facts.weekly_facts import build_weekly_facts
from server.services.training_facts.workout_facts import build_workout_facts


def status_from_action(action: str) -> str:
    return {
        "block_auto_apply": "auto_apply_blocked",
        "require_user_review": "needs_review",
        "rest_recommended": "needs_review",
        "downgrade_recommended": "adjustment_recommended",
        "adjust_recommended": "adjustment_recommended",
        "monitor": "passed_with_notice",
        "show_info": "passed_with_notice",
    }.get(action, "passed")


def title_from_action(action: str) -> str:
    return {
        "no_action": "暂无额外建议",
        "show_info": "信息提示",
        "keep_plan": "按计划执行",
        "monitor": "注意观察",
        "adjust_recommended": "建议调整",
        "downgrade_recommended": "建议降低强度",
        "rest_recommended": "建议休息",
        "require_user_review": "需要重新确认",
        "block_auto_apply": "已阻止自动应用",
        "workout_completed_as_planned": "按计划完成",
        "workout_completed_with_adjustment": "调整后完成",
        "workout_load_higher_than_planned": "负荷高于计划",
        "workout_load_lower_than_planned": "负荷低于计划",
        "workout_incomplete": "训练未完整完成",
        "recovery_attention_recommended": "建议关注恢复",
        "next_workout_review_required": "建议复核下一次训练",
    }.get(action, "训练管理提示")


def _summary(evaluation: TrainingRuleEvaluateResponse) -> RuleLoopSummary:
    counts = RuleLoopSummary()
    for hit in evaluation.matched_rules:
        if hasattr(counts, hit.severity):
            setattr(counts, hit.severity, getattr(counts, hit.severity) + 1)
    return counts


def _message(evaluation: TrainingRuleEvaluateResponse) -> str:
    if evaluation.matched_rules:
        return evaluation.matched_rules[0].explanation
    return "根据当前已记录的数据，暂未触发需要调整的规则。该结果用于训练管理参考，不构成医疗诊断。"


def _wrap(evaluation: TrainingRuleEvaluateResponse, facts: dict[str, Any], draft_id: int | None = None) -> RuleLoopEvaluationResponse:
    return RuleLoopEvaluationResponse(
        validation_status=status_from_action(evaluation.final_action),
        title=title_from_action(evaluation.final_action),
        message=_message(evaluation),
        data_limited=bool(facts.get("system", {}).get("data_limited")),
        summary=_summary(evaluation),
        evaluation=evaluation,
        facts_hash=hash_facts(facts),
        generated_adjustment_draft_id=draft_id,
    )


def validate_cycle_plan(db: Session, user_id: int, cycle_id: int, *, force: bool = False) -> RuleLoopEvaluationResponse:
    facts = build_cycle_plan_facts(db, user_id, cycle_id)
    evaluation, _ = training_rule_service.evaluate_standard_facts(
        db,
        user_id=user_id,
        context_type="plan_validation",
        context_id=f"cycle:{cycle_id}",
        facts=facts,
        force=force,
    )
    return _wrap(evaluation, facts)


def validate_ai_plan_draft(db: Session, user_id: int, draft_id: int, *, force: bool = False) -> RuleLoopEvaluationResponse:
    facts = build_ai_draft_plan_facts(db, user_id, draft_id)
    evaluation, _ = training_rule_service.evaluate_standard_facts(
        db,
        user_id=user_id,
        context_type="plan_validation",
        context_id=f"ai_plan_draft:{draft_id}",
        facts=facts,
        force=force,
    )
    return _wrap(evaluation, facts)


def validate_plan_import_draft(db: Session, user_id: int, import_id: int, *, force: bool = False) -> RuleLoopEvaluationResponse:
    facts = build_plan_import_facts(db, user_id, import_id)
    evaluation, _ = training_rule_service.evaluate_standard_facts(
        db,
        user_id=user_id,
        context_type="plan_validation",
        context_id=f"plan_import_draft:{import_id}",
        facts=facts,
        force=force,
    )
    return _wrap(evaluation, facts)


def evaluate_today(db: Session, user_id: int, target_date: date, *, force: bool = False) -> RuleLoopEvaluationResponse:
    facts = build_daily_facts(db, user_id, target_date)
    evaluation, model = training_rule_service.evaluate_standard_facts(
        db,
        user_id=user_id,
        context_type="daily_adjustment",
        context_id=target_date.isoformat(),
        facts=facts,
        force=force,
    )
    response = _wrap(evaluation, facts)
    response.evaluated_at = model.created_at if model else None  # type: ignore[attr-defined]
    return response


def evaluate_today_readonly(
    db: Session,
    user_id: int,
    target_date: date,
) -> RuleLoopEvaluationResponse:
    """Evaluate today's existing facts without evaluations, hits, or drafts."""
    facts = build_daily_facts(db, user_id, target_date)
    evaluation, _ = training_rule_service.evaluate_standard_facts(
        db,
        user_id=user_id,
        context_type="daily_adjustment",
        context_id=target_date.isoformat(),
        facts=facts,
        persist=False,
        public_only=True,
    )
    return _wrap(evaluation, facts)


def review_workout_log(db: Session, user_id: int, workout_log_id: int, *, force: bool = False) -> RuleLoopEvaluationResponse:
    facts = build_workout_facts(db, user_id, workout_log_id)
    evaluation, _ = training_rule_service.evaluate_standard_facts(
        db,
        user_id=user_id,
        context_type="workout_review",
        context_id=str(workout_log_id),
        facts=facts,
        force=force,
    )
    return _wrap(evaluation, facts)


def evaluate_weekly_rules(
    db: Session,
    user_id: int,
    cycle_id: int,
    source_block_id: int,
    target_block_id: int | None,
    *,
    force: bool = False,
) -> RuleLoopEvaluationResponse:
    facts = build_weekly_facts(db, user_id, cycle_id, source_block_id, target_block_id)
    context_id = f"{cycle_id}:{source_block_id}:{target_block_id or 'none'}"
    evaluation, model = training_rule_service.evaluate_standard_facts(
        db,
        user_id=user_id,
        context_type="weekly_review",
        context_id=context_id,
        facts=facts,
        force=force,
    )
    draft_id = None
    if model is not None and target_block_id is not None:
        draft = create_weekly_adjustment_draft(db, user_id, model, facts, evaluation)
        draft_id = draft.id
    return _wrap(evaluation, facts, draft_id=draft_id)


def create_weekly_adjustment_draft(
    db: Session,
    user_id: int,
    evaluation: TrainingRuleEvaluation,
    facts: dict[str, Any],
    result: TrainingRuleEvaluateResponse,
) -> TrainingAdjustmentDraft:
    existing = db.scalar(
        select(TrainingAdjustmentDraft).where(
            TrainingAdjustmentDraft.user_id == user_id,
            TrainingAdjustmentDraft.source_evaluation_id == evaluation.id,
        )
    )
    if existing is not None:
        return existing
    adjustment = _weekly_adjustment_from_rules(result, facts)
    draft = TrainingAdjustmentDraft(
        user_id=user_id,
        source_type="weekly_review",
        source_evaluation_id=evaluation.id,
        cycle_id=facts["system"].get("cycle_id"),
        week_start=_week_start(facts),
        status="draft",
        adjustment_json=adjustment,
        explanation_json={
            "title": title_from_action(result.final_action),
            "message": _message(result),
            "matched_rule_codes": [hit.rule_code for hit in result.matched_rules],
        },
        original_plan_snapshot_json={"next_week": facts.get("plan", {}).get("next_week", {})},
        facts_hash=evaluation.facts_hash,
        source_version=SOURCE_VERSION,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def _weekly_adjustment_from_rules(result: TrainingRuleEvaluateResponse, facts: dict[str, Any]) -> dict[str, Any]:
    codes = {hit.rule_code for hit in result.matched_rules}
    has_pain_or_alert = bool(codes & {"WEEK_PAIN_REPORTED_REVIEW_REQUIRED", "WEEK_TRAINING_ALERT_REVIEW_REQUIRED"})
    return {
        "volume_action": "reduce" if has_pain_or_alert or "WEEK_HIGH_LOAD_RECOVERY_NOTICE" in codes else "keep",
        "volume_change_ratio": -0.1 if has_pain_or_alert else 0,
        "intensity_action": "remove_one_key_session" if "WEEK_TOO_MANY_KEY_SESSIONS_NEXT_WEEK" in codes else "keep",
        "long_run_action": "keep_long_run",
        "recovery_action": "add_rest_day" if "WEEK_ADD_REST_DAY_RECOMMENDED" in codes or has_pain_or_alert else "keep",
        "reason_codes": sorted(codes),
        "requires_manual_review": result.final_action in {"require_user_review", "block_auto_apply"},
    }


def _week_start(facts: dict[str, Any]) -> date | None:
    value = facts.get("weekly", {}).get("week_start_date")
    return date.fromisoformat(value) if value else None


def list_adjustment_drafts(db: Session, user_id: int, *, limit: int = 50, offset: int = 0) -> tuple[list[TrainingAdjustmentDraft], int]:
    total = db.scalar(select(func.count()).select_from(TrainingAdjustmentDraft).where(TrainingAdjustmentDraft.user_id == user_id)) or 0
    items = list(
        db.scalars(
            select(TrainingAdjustmentDraft)
            .where(TrainingAdjustmentDraft.user_id == user_id)
            .order_by(TrainingAdjustmentDraft.created_at.desc(), TrainingAdjustmentDraft.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def get_adjustment_draft(db: Session, user_id: int, draft_id: int) -> TrainingAdjustmentDraft:
    draft = db.scalar(select(TrainingAdjustmentDraft).where(TrainingAdjustmentDraft.id == draft_id, TrainingAdjustmentDraft.user_id == user_id))
    if draft is None:
        raise NotFoundError("Training adjustment draft not found.")
    return draft


def confirm_adjustment_draft(db: Session, user_id: int, draft_id: int) -> TrainingAdjustmentDraft:
    draft = get_adjustment_draft(db, user_id, draft_id)
    if draft.status not in {"draft", "confirmed"}:
        raise BadRequestError("This adjustment draft cannot be confirmed.")
    draft.status = "confirmed"
    db.commit()
    db.refresh(draft)
    return draft


def reject_adjustment_draft(db: Session, user_id: int, draft_id: int) -> TrainingAdjustmentDraft:
    draft = get_adjustment_draft(db, user_id, draft_id)
    if draft.status == "applied":
        raise BadRequestError("Applied draft cannot be rejected.")
    draft.status = "rejected"
    db.commit()
    db.refresh(draft)
    return draft


def apply_adjustment_draft(db: Session, user_id: int, draft_id: int) -> TrainingAdjustmentDraft:
    draft = get_adjustment_draft(db, user_id, draft_id)
    if draft.status == "applied":
        raise BadRequestError("Adjustment draft already applied.")
    if draft.status in {"rejected", "expired", "failed"}:
        raise BadRequestError("This adjustment draft cannot be applied.")
    snapshot_workouts = draft.original_plan_snapshot_json.get("next_week", {}).get("workouts", [])
    current = {
        item.id: item
        for item in db.scalars(
            select(PlannedWorkout).where(
                PlannedWorkout.user_id == user_id,
                PlannedWorkout.id.in_([item["id"] for item in snapshot_workouts if item.get("id")]),
            )
        )
    }
    for item in snapshot_workouts:
        workout = current.get(item.get("id"))
        if workout is None or workout.plan_version != item.get("plan_version"):
            draft.status = "expired"
            db.commit()
            raise BadRequestError("Original plan has changed. Please regenerate the adjustment draft.")
    applied_changes = _apply_weekly_adjustment(db, draft, current)
    draft.status = "applied"
    draft.applied_at = datetime.utcnow()
    draft.applied_result_json = {
        "applied": bool(applied_changes),
        "message": "Adjustment draft applied with conservative v0.10.1 actions.",
        "checked_workout_count": len(snapshot_workouts),
        "changes": applied_changes,
    }
    db.commit()
    db.refresh(draft)
    return draft


def _apply_weekly_adjustment(
    db: Session,
    draft: TrainingAdjustmentDraft,
    current: dict[int, PlannedWorkout],
) -> list[dict[str, Any]]:
    if draft.source_type != "weekly_review":
        raise BadRequestError("Only weekly review adjustment drafts can be applied in v0.10.1.")
    adjustment = draft.adjustment_json or {}
    workouts = sorted(
        current.values(),
        key=lambda item: (item.workout_date or date.max, item.session_index or 1, item.id),
    )
    changes: list[dict[str, Any]] = []
    changed_ids: set[int] = set()

    if adjustment.get("intensity_action") in {"remove_one_key_session", "downgrade_one_key_session"}:
        target = next(
            (item for item in workouts if not item.is_locked and is_high_intensity(enum_value(item.main_type_normalized))),
            None,
        )
        if target is not None:
            original_type = enum_value(target.main_type_normalized)
            target.main_type_normalized = WorkoutMainTypeNormalized.easy
            target.planned_content = f"轻松跑 / 恢复跑（由规则调整草稿降级）：{target.planned_content}"
            target.plan_version += 1
            changed_ids.add(target.id)
            changes.append({"workout_id": target.id, "action": "downgrade_key_session", "from_type": original_type, "to_type": "easy"})

    if adjustment.get("recovery_action") == "add_rest_day":
        target = next(
            (
                item
                for item in workouts
                if not item.is_locked
                and item.id not in changed_ids
                and not is_high_intensity(enum_value(item.main_type_normalized))
                and enum_value(item.main_type_normalized) != "rest"
            ),
            None,
        ) or next((item for item in workouts if not item.is_locked and item.id not in changed_ids), None)
        if target is not None:
            original_type = enum_value(target.main_type_normalized)
            original_distance = decimal_float(target.planned_distance_km) or 0
            target.main_type_normalized = WorkoutMainTypeNormalized.rest
            target.planned_distance_km = 0
            target.planned_content = f"休息（由规则调整草稿建议）：{target.planned_content}"
            target.plan_version += 1
            changed_ids.add(target.id)
            changes.append(
                {
                    "workout_id": target.id,
                    "action": "add_rest_day",
                    "from_type": original_type,
                    "from_distance_km": original_distance,
                    "to_distance_km": 0,
                }
            )

    ratio = float(adjustment.get("volume_change_ratio") or 0)
    if adjustment.get("volume_action") == "reduce" and ratio < 0:
        safe_ratio = max(ratio, -0.15)
        multiplier = 1 + safe_ratio
        for item in workouts:
            if item.is_locked or item.id in changed_ids or enum_value(item.main_type_normalized) == "rest":
                continue
            original_distance = decimal_float(item.planned_distance_km)
            if original_distance is None or original_distance <= 0:
                continue
            new_distance = round(max(0, original_distance * multiplier), 2)
            if new_distance == original_distance:
                continue
            item.planned_distance_km = new_distance
            item.plan_version += 1
            changes.append(
                {
                    "workout_id": item.id,
                    "action": "reduce_distance",
                    "from_distance_km": original_distance,
                    "to_distance_km": new_distance,
                }
            )

    if changes:
        db.flush()
    return changes
