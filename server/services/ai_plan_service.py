from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
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
)
from planner_core.enums import AIPlanDraftStatus, AIPlanJobStatus, BlockType, WorkoutStatusNormalized
from planner_core.utils.excel_parse import normalize_workout_main_type
from server.common.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError, TooManyRequestsError
from server.schemas.ai_plan import AIPlanGenerateRequest, AIPlanQuotaRead
from server.services.admin_ai_settings_service import EffectiveAISettings, get_effective_ai_settings
from server.services.ai_coach_preference_service import (
    get_or_create_preference,
    preference_to_prompt_dict,
)
from server.services.ai_plan_prompt import build_ai_plan_system_prompt, build_ai_plan_user_prompt

MAX_INPUT_JSON_CHARS = 20000
ALLOWED_MAIN_TYPES = {"REC", "E", "LSD", "M", "T1", "T2", "I", "R", "Rest", "Mixed"}
HIGH_INTENSITY_TYPES = {"T1", "T2", "I", "R", "Mixed"}


@dataclass(frozen=True)
class DeepSeekResult:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


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
    if quota.last_generated_at is not None:
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
    if quota.last_generated_at is not None:
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
    return min(max(4096, plan_weeks * runtime.max_tokens_per_week), runtime.max_tokens_cap)


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
    response = client.chat.completions.create(
        model=runtime.ai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=runtime.temperature,
        top_p=runtime.top_p,
        max_tokens=calculate_max_tokens(plan_weeks, runtime),
    )
    content = response.choices[0].message.content if response.choices else ""
    usage = getattr(response, "usage", None)
    return DeepSeekResult(
        content=content or "",
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
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
    return BadRequestError(f"AI 课表生成失败：{message}")


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
                    focus_note=workout.get("focus_note") or week.get("focus"),
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
    input_json = {
        **canonical_input(payload),
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
    job = save_job(db, user_id, runtime.ai_model, prompt_hash, input_json)
    system_prompt = build_ai_plan_system_prompt()
    user_prompt = build_ai_plan_user_prompt(payload, preference_json)
    try:
        result = call_deepseek(system_prompt, user_prompt, payload.plan_weeks, runtime)
        output = validate_ai_output(result.content, expected_plan_weeks=payload.plan_weeks)
        job.output_json = output
        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.total_tokens = result.total_tokens
        job.status = AIPlanJobStatus.success
        job.finished_at = datetime.utcnow()
        quota.used_count += 1
        quota.last_generated_at = datetime.utcnow()
        db.commit()
        return save_draft(db, job, output)
    except Exception as exc:
        job.status = AIPlanJobStatus.failed
        job.error_message = str(exc)
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


def apply_draft_to_training_plan(db: Session, draft_id: int, user_id: int) -> TrainingCycle:
    draft = get_draft(db, draft_id, user_id)
    if draft.status == AIPlanDraftStatus.accepted:
        raise BadRequestError("草稿已经应用过，不能重复应用。")
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
    )
    db.add(cycle)
    db.flush()

    blocks: dict[str, TrainingBlock] = {}
    for workout in draft.workouts:
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
    db.commit()
    db.refresh(cycle)
    return cycle
