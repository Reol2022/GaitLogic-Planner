from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo
from planner_core.config import get_settings

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import (
    AIPlanDraft,
    AIPlanDraftWorkout,
    AIPlanJob,
    AIPlanQuota,
    PlannedWorkout,
    TrainingBlock,
    TrainingCycle,
    WorkoutLog,
    UserAccount,
)
from planner_core.enums import AIPlanDraftStatus, AIPlanJobStatus, BlockType, WorkoutStatusNormalized, TrainingCycleStatus
from planner_core.utils.excel_parse import normalize_workout_main_type
from server.common.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError, TooManyRequestsError
from server.schemas.ai_plan import AIPlanGenerateRequest, AIPlanQuotaRead
from server.services.admin_ai_settings_service import EffectiveAISettings, get_effective_ai_settings
from server.services.ai_coach_preference_service import (
    get_or_create_preference,
    preference_to_prompt_dict,
)
from server.services.ai_plan_prompt import build_ai_plan_system_prompt, build_ai_plan_user_prompt
from server.model_tasks import ModelTaskType, task_model_profile
from server.services.ai_plan_context_service import build_plan_context
from server.services.ai_plan_constraints import validate_plan_constraints
from server.services.ai_plan_calendar import plan_calendar

MAX_INPUT_JSON_CHARS = 20000
ALLOWED_MAIN_TYPES = {"REC", "E", "LSD", "M", "T1", "T2", "I", "R", "Rest", "Mixed"}
HIGH_INTENSITY_TYPES = {"T1", "T2", "I", "R", "Mixed"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeepSeekResult:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    reasoning_length: int = 0


class AIPlanOutputError(BadRequestError):
    def __init__(self, category: str, reason: str):
        self.category = category
        super().__init__(
            f'模型已返回课表，但{reason}。本次未保存为可应用草稿，未扣除成功生成额度。',
            error_code='AI_PLAN_' + category,
        )


def canonical_input(payload: AIPlanGenerateRequest) -> dict[str, Any]:
    return payload.model_dump(mode="json")


def prompt_hash_for_input(input_json: dict[str, Any]) -> str:
    raw = json.dumps(input_json, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(raw) > MAX_INPUT_JSON_CHARS:
        raise BadRequestError("AI 课表输入过长，请减少备注内容。")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_or_create_today_quota(db: Session, user_id: int) -> AIPlanQuota:
    runtime = get_effective_ai_settings(db)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    quota = db.scalar(
        select(AIPlanQuota).where(AIPlanQuota.user_id == user_id, AIPlanQuota.quota_date == today)
    )
    if quota is None:
        quota = AIPlanQuota(
            user_id=user_id,
            quota_date=today,
            daily_limit=runtime.ai_plan_daily_limit,
            used_count=0,
        )
        db.add(quota)
        db.flush()
    return quota


def check_ai_plan_quota(db: Session, user_id: int) -> AIPlanQuota:
    runtime = get_effective_ai_settings(db)
    quota = get_or_create_today_quota(db, user_id)
    quota.daily_limit = runtime.ai_plan_daily_limit
    if quota.used_count >= quota.daily_limit:
        raise TooManyRequestsError("今日 AI 课表生成次数已用完。")
    if runtime.ai_plan_cooldown_seconds > 0 and quota.last_generated_at is not None:
        elapsed = (datetime.utcnow() - quota.last_generated_at).total_seconds()
        if elapsed < runtime.ai_plan_cooldown_seconds:
            raise TooManyRequestsError("AI 课表生成过于频繁，请稍后再试。")
    return quota


def get_quota_status(db: Session, user_id: int) -> AIPlanQuotaRead:
    runtime = get_effective_ai_settings(db)
    quota = get_or_create_today_quota(db, user_id)
    quota.daily_limit = runtime.ai_plan_daily_limit
    remaining = max(quota.daily_limit - quota.used_count, 0)
    can_generate = remaining > 0
    if runtime.ai_plan_cooldown_seconds > 0 and quota.last_generated_at is not None:
        elapsed = (datetime.utcnow() - quota.last_generated_at).total_seconds()
        if elapsed < runtime.ai_plan_cooldown_seconds:
            can_generate = False
    db.commit()
    return AIPlanQuotaRead(
        model_name=runtime.ai_model,
        daily_limit=quota.daily_limit,
        used_count=quota.used_count,
        remaining_count=remaining,
        last_generated_at=quota.last_generated_at,
        cooldown_seconds=runtime.ai_plan_cooldown_seconds,
        can_generate=can_generate,
    )


def return_cached_draft_if_same_prompt(db: Session, user_id: int, prompt_hash: str) -> AIPlanDraft | None:
    since = datetime.utcnow() - timedelta(hours=24)
    job = db.scalar(
        select(AIPlanJob)
        .options(selectinload(AIPlanJob.draft).selectinload(AIPlanDraft.workouts))
        .where(
            AIPlanJob.user_id == user_id,
            AIPlanJob.prompt_hash == prompt_hash,
            AIPlanJob.status == AIPlanJobStatus.success,
            AIPlanJob.created_at >= since,
        )
        .order_by(AIPlanJob.created_at.desc(), AIPlanJob.id.desc())
    )
    if job and job.draft:
        job.draft.workouts.sort(key=lambda workout: workout.sort_order)
        return job.draft
    return None


def save_job(db: Session, user_id: int, model_name: str, prompt_hash: str, input_json: dict[str, Any]) -> AIPlanJob:
    job = AIPlanJob(
        user_id=user_id,
        status=AIPlanJobStatus.running,
        model_name=model_name,
        prompt_hash=prompt_hash,
        input_json=input_json,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def calculate_max_tokens(plan_weeks: int, runtime: EffectiveAISettings) -> int:
    del plan_weeks, runtime
    return task_model_profile(get_settings(), ModelTaskType.AI_PLAN_GENERATION).max_output_tokens


def call_ai_model(
    system_prompt: str,
    user_prompt: str,
    plan_weeks: int,
    runtime: EffectiveAISettings,
) -> DeepSeekResult:
    if not runtime.ai_api_key:
        raise BadRequestError("AI_API_KEY is not configured.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise BadRequestError("OpenAI-compatible SDK is not installed.") from exc

    client = OpenAI(
        api_key=runtime.ai_api_key,
        base_url=runtime.ai_base_url,
        timeout=runtime.ai_timeout_seconds,
    )
    profile = task_model_profile(get_settings(), ModelTaskType.AI_PLAN_GENERATION)
    response = client.chat.completions.create(
        model=runtime.ai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=runtime.temperature,
        top_p=runtime.top_p,
        max_tokens=calculate_max_tokens(plan_weeks, runtime),
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "enabled" if profile.thinking_enabled else "disabled"}},
    )
    choice = response.choices[0] if response.choices else None
    content = choice.message.content if choice else ""
    reasoning = getattr(choice.message, "reasoning_content", None) if choice else ""
    usage = getattr(response, "usage", None)
    return DeepSeekResult(
        content=content or "",
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
        finish_reason=getattr(choice, "finish_reason", None),
        reasoning_length=len(reasoning or ""),
    )


call_deepseek = call_ai_model


def normalize_ai_generation_exception(exc: Exception) -> Exception:
    status_code = getattr(exc, "status_code", None)
    message = str(exc)
    lowered = message.lower()
    if status_code == 402 or "insufficient balance" in lowered:
        return BadRequestError("AI 服务账户余额不足，请充值或更换可用 API Key。")
    if status_code in {500, 501, 502, 503, 504}:
        return ServiceUnavailableError("AI 模型服务暂时不可用，请稍后在历史草稿中查看结果或重新生成。")
    if "timeout" in lowered or "timed out" in lowered or "read timed out" in lowered:
        return ServiceUnavailableError("AI 模型响应超时，请稍后在历史草稿中查看结果或重新生成。")
    return BadRequestError("AI 课表生成失败，请稍后重试或联系管理员检查安全错误类别。")


def parse_json_date(value: Any, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise BadRequestError(f"{field_name} must be a date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise BadRequestError(f"{field_name} format must be YYYY-MM-DD.") from exc


def load_ai_json(output: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(output, dict):
        return output
    stripped = output.strip()
    if stripped.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
        if not match:
            raise BadRequestError("AI output must be raw JSON, not Markdown.")
        stripped = match.group(1).strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise BadRequestError("AI output is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise BadRequestError("AI output must be a JSON object.")
    return data


def validate_ai_output(
    output: str | dict[str, Any],
    expected_plan_weeks: int | None = None,
) -> dict[str, Any]:
    data = load_ai_json(output)
    if "weeks" not in data:
        raise BadRequestError("AI output missing required field: weeks.")
    if not isinstance(data["weeks"], list) or not data["weeks"]:
        raise BadRequestError("AI output weeks must be a non-empty list.")
    if expected_plan_weeks is not None and len(data["weeks"]) != expected_plan_weeks:
        raise BadRequestError(
            f"AI output weeks count mismatch: expected {expected_plan_weeks}, got {len(data['weeks'])}."
        )

    parse_json_date(data.get("start_date"), "start_date")
    parse_json_date(data.get("end_date"), "end_date")
    parse_json_date(data.get("target_race_date"), "target_race_date")

    for week_index, week in enumerate(data["weeks"], start=1):
        if not isinstance(week, dict):
            raise BadRequestError(f"Week {week_index} must be an object.")
        if not isinstance(week.get("workouts"), list):
            raise BadRequestError(f"Week {week_index} workouts must be a list.")
        planned_week_km = week.get("planned_distance_km", 0)
        if not isinstance(planned_week_km, (int, float)):
            raise BadRequestError("planned_distance_km must be numeric.")

        previous_high_intensity = False
        previous_date: date | None = None
        for workout_index, workout in enumerate(week["workouts"], start=1):
            if not isinstance(workout, dict):
                raise BadRequestError(f"Workout {workout_index} must be an object.")
            workout_date = parse_json_date(workout.get("date"), "workout.date")
            planned_km = workout.get("planned_distance_km", 0)
            if planned_km is not None and not isinstance(planned_km, (int, float)):
                raise BadRequestError("planned_distance_km must be numeric.")
            if not workout.get("planned_content"):
                raise BadRequestError("workout planned_content is required.")
            if "target_pace_text" not in workout:
                raise BadRequestError("workout target_pace_text is required.")

            main_type = workout.get("main_type")
            if main_type not in ALLOWED_MAIN_TYPES:
                raise BadRequestError(f"Invalid main_type: {main_type}.")
            if main_type != "Rest" and not workout.get("focus_note"):
                raise BadRequestError("workout focus_note is required for non-rest workouts.")

            is_high_intensity = main_type in HIGH_INTENSITY_TYPES
            if (
                is_high_intensity
                and previous_high_intensity
                and previous_date is not None
                and workout_date is not None
                and (workout_date - previous_date).days == 1
            ):
                raise BadRequestError("AI output has consecutive high-intensity workouts.")
            previous_high_intensity = is_high_intensity
            previous_date = workout_date

    return data


def validate_generated_plan(content: str, payload: AIPlanGenerateRequest, disabled_types=()) -> dict:
    """Only fill absent request metadata; never rewrite workouts or conflicts."""
    try:
        data = dict(load_ai_json(content))
    except BadRequestError:
        raise AIPlanOutputError('OUTPUT_PARSE_FAILED', '返回内容不是完整有效的 JSON') from None
    calendar = plan_calendar(payload.plan_start_date, payload.plan_weeks, payload.target_race_date)
    # These are authoritative user inputs, not invented model training facts.
    for key, value in {
        'start_date': payload.plan_start_date.isoformat(), 'end_date': calendar.end.isoformat(),
        'target_race_date': payload.target_race_date.isoformat() if payload.target_race_date else None,
        'target_result': payload.target_result, 'target_distance': payload.target_distance.value,
    }.items():
        data.setdefault(key, value)
    try:
        validate_ai_output(data, expected_plan_weeks=payload.plan_weeks)
    except BadRequestError as exc:
        if exc.message == 'AI output has consecutive high-intensity workouts.':
            raise AIPlanOutputError('SAFETY_BOUNDARY', '安排了连续两天高强度训练，已按训练安全规则拦截') from None
        # Do not expose model-supplied field values or raw parser exceptions.
        reasons = {
            'planned_distance_km must be numeric.': '训练距离字段不是数字',
            'workout planned_content is required.': '缺少具体训练内容',
            'workout target_pace_text is required.': '缺少配速字段（无配速建议时也需提供空字段）',
            'workout focus_note is required for non-rest workouts.': '缺少训练目的、执行注意与降级说明',
        }
        if exc.message.startswith('AI output weeks count mismatch:'):
            reason = f'返回周数不等于请求的 {payload.plan_weeks} 周'
        else:
            reason = reasons.get(exc.message, '课表字段、日期或训练类型不符合输出格式')
        raise AIPlanOutputError('OUTPUT_SCHEMA_INVALID', reason) from None
    if not isinstance(data.get('title'), str) or not data['title'].strip() or len(data['title']) > 128:
        raise AIPlanOutputError('OUTPUT_SCHEMA_INVALID', '计划标题缺失或过长')
    risks = data.get('risk_notes')
    if not isinstance(risks, list) or not risks or len(risks) > 30 or any(not isinstance(item,str) or not item.strip() for item in risks):
        raise AIPlanOutputError('OUTPUT_SCHEMA_INVALID', '缺少有效的风险提示列表')
    try:
        validate_plan_constraints(data, payload, disabled_types)
    except BadRequestError as exc:
        # Constraint messages are fixed server-authored explanations, not raw output.
        reason = exc.message.removeprefix('计划未通过约束检查：').rstrip('。')
        raise AIPlanOutputError('CONSTRAINT_VIOLATION', reason) from None
    return data


def generate_validated_plan(system_prompt, user_prompt, payload, runtime, disabled_types=()):
    """At most one schema retry. Safety/constraint violations never retry here."""
    results = []
    prompt = user_prompt
    for attempt in range(2):
        result = call_deepseek(system_prompt, prompt, payload.plan_weeks, runtime)
        results.append(result)
        if result.finish_reason == 'length':
            raise AIPlanOutputError('OUTPUT_TRUNCATED', '模型输出达到长度上限，课表正文不完整；可缩短本次计划周数后再试')
        if not result.content.strip():
            raise AIPlanOutputError('OUTPUT_EMPTY', '模型未返回可用的课表正文')
        try:
            output = validate_generated_plan(result.content, payload, disabled_types)
        except AIPlanOutputError as exc:
            retry = attempt == 0 and exc.category in {'OUTPUT_PARSE_FAILED', 'OUTPUT_SCHEMA_INVALID'}
            logger.warning('ai_plan_output_validation category=%s attempt=%s retry=%s', exc.category, attempt + 1, retry)
            if not retry:
                raise
            prompt = user_prompt + '\n\n上次输出未通过结构校验，原因：' + exc.message.split('。本次')[0] + '。请重新输出完整JSON，严格遵守输出契约与全部训练安全约束，不省略任何周或课程。本次最多进行一次格式重试。'
            continue
        def total(field):
            values = [getattr(item, field) for item in results]
            return sum(values) if all(value is not None for value in values) else None
        usage = DeepSeekResult(content=result.content, input_tokens=total('input_tokens'),
                               output_tokens=total('output_tokens'), total_tokens=total('total_tokens'),
                               finish_reason=result.finish_reason)
        return output, usage
    raise AssertionError('unreachable')


def save_draft(db: Session, job: AIPlanJob, output: dict[str, Any]) -> AIPlanDraft:
    draft = AIPlanDraft(
        user_id=job.user_id,
        job_id=job.id,
        title=output.get("title") or "AI 训练计划草稿",
        goal=output.get("goal"),
        start_date=parse_json_date(output.get("start_date"), "start_date"),
        end_date=parse_json_date(output.get("end_date"), "end_date"),
        target_race_name=output.get("target_race_name"),
        target_race_date=parse_json_date(output.get("target_race_date"), "target_race_date"),
        target_result=output.get("target_result"),
        summary=output.get("summary"),
        risk_notes=output.get("risk_notes") or [],
        status=AIPlanDraftStatus.draft,
    )
    sort_order = 1
    for week in output["weeks"]:
        for workout in week.get("workouts", []):
            main_type_raw = workout.get("main_type") or "UNKNOWN"
            draft.workouts.append(
                AIPlanDraftWorkout(
                    workout_date=parse_json_date(workout.get("date"), "workout.date"),
                    weekday=workout.get("weekday"),
                    block_name=week.get("block_name"),
                    phase_name=week.get("phase_name"),
                    planned_content=workout.get("planned_content"),
                    focus_note=((workout.get("focus_note") or week.get("focus") or '') + (f"\n计划时长：{workout['planned_duration_minutes']} 分钟" if workout.get('planned_duration_minutes') else '')),
                    planned_distance_km=Decimal(str(workout.get("planned_distance_km") or 0)),
                    main_type_raw=main_type_raw,
                    main_type_normalized=normalize_workout_main_type(main_type_raw),
                    target_pace_text=workout.get("target_pace_text"),
                    sort_order=sort_order,
                )
            )
            sort_order += 1

    db.add(draft)
    db.commit()
    return get_draft(db, draft.id, job.user_id)


def generate_ai_plan(db: Session, user_id: int, payload: AIPlanGenerateRequest) -> AIPlanDraft:
    runtime = get_effective_ai_settings(db)
    preference = get_or_create_preference(db, user_id)
    preference_json = preference_to_prompt_dict(preference)
    context = build_plan_context(db, user_id, payload)
    blockers = [issue.message for issue in context.feasibility if issue.severity == 'error']
    if blockers:
        raise BadRequestError('；'.join(blockers), error_code='AI_PLAN_CONSTRAINT_CONFLICT')
    context_json = context.model_dump(mode='json')
    input_json = {
        **canonical_input(payload),
        'ai_plan_output_contract': '2.0.1',
        'plan_context': context_json,
        "ai_coach_preference": preference_json,
        "ai_runtime_settings": {
            "model": runtime.ai_model,
            "base_url": runtime.ai_base_url,
            "daily_limit": runtime.ai_plan_daily_limit,
            "cooldown_seconds": runtime.ai_plan_cooldown_seconds,
            "temperature": runtime.temperature,
            "top_p": runtime.top_p,
        },
    }
    prompt_hash = prompt_hash_for_input(input_json)
    cached = return_cached_draft_if_same_prompt(db, user_id, prompt_hash)
    if cached is not None:
        return cached

    quota = check_ai_plan_quota(db, user_id)
    try:
        job = save_job(db, user_id, runtime.ai_model, prompt_hash, input_json)
    except SQLAlchemyError:
        db.rollback()
        # Do not let a SQL exception expose the private context JSON in generic SQL logs.
        raise ServiceUnavailableError('计划任务暂时无法保存，请稍后重试。') from None
    system_prompt = build_ai_plan_system_prompt()
    user_prompt = build_ai_plan_user_prompt(payload, preference_json, context_json)
    job_id = job.id
    try:
        output, result = generate_validated_plan(system_prompt, user_prompt, payload, runtime,
                                                 preference_json.get('disabled_workout_types', []))
        output['risk_notes'] = list(dict.fromkeys([*(output.get('risk_notes') or []), *[issue.message for issue in context.feasibility]]))
        job.output_json = output
        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.total_tokens = result.total_tokens
        job.status = AIPlanJobStatus.success
        job.finished_at = datetime.utcnow()
        quota.used_count += 1
        quota.last_generated_at = datetime.utcnow()
        return save_draft(db, job, output)
    except Exception as exc:
        db.rollback()
        if isinstance(exc, AIPlanOutputError):
            logger.warning('ai_plan_generation_rejected category=%s plan_weeks=%s', exc.category, payload.plan_weeks)
        job = db.get(AIPlanJob, job_id)
        job.status = AIPlanJobStatus.failed
        job.error_message = getattr(exc, 'message', 'AI provider or persistence failure')[:1000]
        job.finished_at = datetime.utcnow()
        db.commit()
        if isinstance(exc, (BadRequestError, TooManyRequestsError, ServiceUnavailableError)):
            raise
        raise normalize_ai_generation_exception(exc) from exc


def list_drafts(db: Session, user_id: int) -> list[AIPlanDraft]:
    return list(
        db.scalars(
            select(AIPlanDraft)
            .where(AIPlanDraft.user_id == user_id)
            .order_by(AIPlanDraft.created_at.desc(), AIPlanDraft.id.desc())
        )
    )


def get_draft(db: Session, draft_id: int, user_id: int) -> AIPlanDraft:
    draft = db.scalar(
        select(AIPlanDraft)
        .options(selectinload(AIPlanDraft.workouts))
        .where(AIPlanDraft.id == draft_id, AIPlanDraft.user_id == user_id)
    )
    if draft is None:
        raise NotFoundError("AI plan draft not found.")
    draft.workouts.sort(key=lambda workout: workout.sort_order)
    return draft


def reject_draft(db: Session, draft_id: int, user_id: int) -> AIPlanDraft:
    draft = get_draft(db, draft_id, user_id)
    if draft.status == AIPlanDraftStatus.accepted:
        raise BadRequestError("已应用的草稿不能再拒绝。")
    draft.status = AIPlanDraftStatus.rejected
    db.commit()
    db.refresh(draft)
    return get_draft(db, draft.id, user_id)


def apply_draft_to_training_plan(db: Session, draft_id: int, user_id: int, *, activate: bool = False, confirm_high: bool = False) -> TrainingCycle:
    from server.services.training_rule_loop_service import validate_ai_plan_draft
    # Rule evaluation may commit its own audit record. Do it before any business mutation.
    validation = validate_ai_plan_draft(db, user_id, draft_id)
    if validation.evaluation.final_action == 'block_auto_apply':
        raise BadRequestError('规则校验阻止应用，请先修改草稿。')
    if validation.evaluation.final_action == 'require_user_review' and not confirm_high:
        raise BadRequestError('规则校验要求明确确认后再应用。')
    try:
        return _apply_draft_transaction(db, draft_id, user_id, activate=activate)
    except Exception:
        db.rollback()
        raise


def _apply_draft_transaction(db: Session, draft_id: int, user_id: int, *, activate: bool) -> TrainingCycle:
    if db.scalar(select(UserAccount).where(UserAccount.id == user_id).with_for_update()) is None:
        raise NotFoundError('User not found.')
    db.scalar(select(AIPlanDraft).where(AIPlanDraft.id == draft_id, AIPlanDraft.user_id == user_id).with_for_update().execution_options(populate_existing=True))
    draft = get_draft(db, draft_id, user_id)
    if draft.status != AIPlanDraftStatus.draft:
        raise BadRequestError("仅待确认草稿可以应用，不能应用已拒绝或已采用的草稿。")
    if not draft.start_date or not draft.end_date or draft.start_date > draft.end_date or not draft.workouts:
        raise BadRequestError('草稿起止日期或课程不完整。')
    if any(not item.workout_date or not draft.start_date <= item.workout_date <= draft.end_date for item in draft.workouts):
        raise BadRequestError('草稿课程超出周期日期范围。')
    job = db.scalar(select(AIPlanJob).where(AIPlanJob.id == draft.job_id, AIPlanJob.user_id == user_id))
    if job and job.input_json and job.input_json.get('plan_context'):
        request = AIPlanGenerateRequest.model_validate(job.input_json)
        if draft.start_date != request.plan_start_date or draft.end_date != plan_calendar(request.plan_start_date, request.plan_weeks, request.target_race_date).end or draft.target_race_date != request.target_race_date or draft.target_result != job.output_json.get('target_result'):
            raise BadRequestError('草稿目标或日期与用户已确认的约束不同，请重新生成。')
        validate_ai_output(job.output_json, expected_plan_weeks=request.plan_weeks)
        validate_plan_constraints(job.output_json, request, (job.input_json.get('ai_coach_preference') or {}).get('disabled_workout_types', []))
        originals = [item for week in job.output_json['weeks'] for item in week['workouts']]
        if len(originals) != len(draft.workouts) or any(
            original['date'] != saved.workout_date.isoformat()
            or abs(original['planned_distance_km'] - float(saved.planned_distance_km or 0)) > .01
            or original['main_type'] != saved.main_type_raw
            or original['planned_content'] != saved.planned_content
            for original, saved in zip(originals, draft.workouts)
        ):
            raise BadRequestError('草稿明细与已校验输出不同，请重新生成草稿。')
    if activate:
        cycles = list(db.scalars(select(TrainingCycle).where(TrainingCycle.user_id == user_id).with_for_update()))
        if any(item.status == TrainingCycleStatus.active for item in cycles):
            raise BadRequestError('已有启用周期，请先结束当前周期；或选择“仅保存，暂不启用”。')
        for item in cycles:
            if item.status == TrainingCycleStatus.completed:
                start = item.actual_start_date or item.start_date
                end = item.actual_end_date or item.end_date
                if start and end and start <= draft.end_date and end >= draft.start_date:
                    raise BadRequestError('新计划与已完成周期的日期重叠，请先调整日期。')
    existing = db.scalar(
        select(TrainingCycle).where(TrainingCycle.user_id == user_id, TrainingCycle.name == draft.title)
    )
    if existing is not None:
        raise BadRequestError("同名训练周期已存在，请先修改草稿标题或删除已有周期。")

    cycle = TrainingCycle(
        user_id=user_id,
        name=draft.title,
        goal=draft.goal,
        start_date=draft.start_date,
        end_date=draft.end_date,
        target_race_name=draft.target_race_name,
        target_race_date=draft.target_race_date,
        target_result=draft.target_result,
        description=draft.summary,
        status=TrainingCycleStatus.draft,
    )
    db.add(cycle)
    db.flush()

    blocks: dict[str, TrainingBlock] = {}
    session_indices: dict[date, int] = {}
    for workout in draft.workouts:
        session_indices[workout.workout_date] = session_indices.get(workout.workout_date, 0) + 1
        block_key = workout.block_name or "AI 训练块"
        if block_key not in blocks:
            block = TrainingBlock(
                user_id=user_id,
                cycle_id=cycle.id,
                block_name=block_key,
                block_type=BlockType.week,
                sort_order=len(blocks) + 1,
                phase_name=workout.phase_name,
                focus=workout.focus_note,
            )
            db.add(block)
            db.flush()
            blocks[block_key] = block
        block = blocks[block_key]
        focus_note = workout.focus_note
        if workout.target_pace_text:
            focus_note = f"{focus_note or ''}\n目标配速：{workout.target_pace_text}".strip()
        db.add(
            PlannedWorkout(
                user_id=user_id,
                cycle_id=cycle.id,
                block_id=block.id,
                workout_date=workout.workout_date,
                session_index=session_indices[workout.workout_date],
                date_text=workout.workout_date.isoformat(),
                weekday=workout.weekday,
                month_text=f"{workout.workout_date.month}月",
                phase_name=workout.phase_name,
                planned_content=workout.planned_content,
                focus_note=focus_note,
                target_pace_text=workout.target_pace_text,
                planned_distance_km=workout.planned_distance_km,
                main_type_raw=workout.main_type_raw,
                main_type_normalized=workout.main_type_normalized,
                source_sheet="AI_PLAN_DRAFT",
                source_row=workout.sort_order,
                sort_order=workout.sort_order,
                workout_log=WorkoutLog(
                    user_id=user_id,
                    status_raw=None,
                    status_normalized=WorkoutStatusNormalized.not_started,
                ),
            )
        )

    draft.status = AIPlanDraftStatus.accepted
    if activate:
        # Reuse lifecycle status invariants; do not let it commit a partial application.
        from server.services.training_cycle_lifecycle_service import activate_cycle
        from server.schemas.training_cycle import TrainingCycleActivateRequest
        db.flush()
        activate_cycle(db, user_id, cycle.id, TrainingCycleActivateRequest(effective_start_date=cycle.start_date, complete_current_cycle=False), commit=False)
    db.commit()
    db.refresh(cycle)
    return cycle
