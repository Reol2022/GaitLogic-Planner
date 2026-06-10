from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.models import AdminAISettings
from server.schemas.admin_ai_settings import AdminAISettingsRead, AdminAISettingsUpdate

SETTINGS_ROW_ID = 1


@dataclass(frozen=True)
class EffectiveAISettings:
    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str
    deepseek_timeout_seconds: int
    ai_plan_daily_limit: int
    ai_plan_cooldown_seconds: int
    temperature: float
    top_p: float
    max_tokens_per_week: int
    max_tokens_cap: int


def get_or_create_admin_ai_settings(db: Session) -> AdminAISettings:
    settings = get_settings()
    row = db.scalar(select(AdminAISettings).where(AdminAISettings.id == SETTINGS_ROW_ID))
    if row is not None:
        return row

    row = AdminAISettings(
        id=SETTINGS_ROW_ID,
        deepseek_base_url=settings.deepseek_base_url,
        deepseek_model=settings.deepseek_model,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_timeout_seconds=settings.deepseek_timeout_seconds,
        ai_plan_daily_limit=settings.ai_plan_daily_limit,
        ai_plan_cooldown_seconds=settings.ai_plan_cooldown_seconds,
        temperature=Decimal("0.40"),
        top_p=Decimal("0.90"),
        max_tokens_per_week=1600,
        max_tokens_cap=24000,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def to_read_schema(row: AdminAISettings) -> AdminAISettingsRead:
    return AdminAISettingsRead(
        id=row.id,
        deepseek_base_url=row.deepseek_base_url,
        deepseek_model=row.deepseek_model,
        deepseek_timeout_seconds=row.deepseek_timeout_seconds,
        ai_plan_daily_limit=row.ai_plan_daily_limit,
        ai_plan_cooldown_seconds=row.ai_plan_cooldown_seconds,
        temperature=float(row.temperature),
        top_p=float(row.top_p),
        max_tokens_per_week=row.max_tokens_per_week,
        max_tokens_cap=row.max_tokens_cap,
        has_api_key=bool(row.deepseek_api_key),
        api_key_preview=mask_api_key(row.deepseek_api_key),
        updated_at=row.updated_at,
    )


def get_admin_ai_settings(db: Session) -> AdminAISettingsRead:
    return to_read_schema(get_or_create_admin_ai_settings(db))


def update_admin_ai_settings(
    db: Session,
    payload: AdminAISettingsUpdate,
    admin_user_id: int,
) -> AdminAISettingsRead:
    row = get_or_create_admin_ai_settings(db)
    row.deepseek_base_url = payload.deepseek_base_url
    row.deepseek_model = payload.deepseek_model
    if payload.deepseek_api_key is not None:
        row.deepseek_api_key = payload.deepseek_api_key.strip() or None
    row.deepseek_timeout_seconds = payload.deepseek_timeout_seconds
    row.ai_plan_daily_limit = payload.ai_plan_daily_limit
    row.ai_plan_cooldown_seconds = payload.ai_plan_cooldown_seconds
    row.temperature = Decimal(str(payload.temperature))
    row.top_p = Decimal(str(payload.top_p))
    row.max_tokens_per_week = payload.max_tokens_per_week
    row.max_tokens_cap = payload.max_tokens_cap
    row.updated_by_id = admin_user_id
    db.commit()
    db.refresh(row)
    return to_read_schema(row)


def get_effective_ai_settings(db: Session | None = None) -> EffectiveAISettings:
    env_settings = get_settings()
    if db is None:
        return EffectiveAISettings(
            deepseek_api_key=env_settings.deepseek_api_key,
            deepseek_base_url=env_settings.deepseek_base_url,
            deepseek_model=env_settings.deepseek_model,
            deepseek_timeout_seconds=env_settings.deepseek_timeout_seconds,
            ai_plan_daily_limit=env_settings.ai_plan_daily_limit,
            ai_plan_cooldown_seconds=env_settings.ai_plan_cooldown_seconds,
            temperature=0.4,
            top_p=0.9,
            max_tokens_per_week=1600,
            max_tokens_cap=24000,
        )

    row = get_or_create_admin_ai_settings(db)
    return EffectiveAISettings(
        deepseek_api_key=row.deepseek_api_key or env_settings.deepseek_api_key,
        deepseek_base_url=row.deepseek_base_url or env_settings.deepseek_base_url,
        deepseek_model=row.deepseek_model or env_settings.deepseek_model,
        deepseek_timeout_seconds=row.deepseek_timeout_seconds or env_settings.deepseek_timeout_seconds,
        ai_plan_daily_limit=row.ai_plan_daily_limit,
        ai_plan_cooldown_seconds=row.ai_plan_cooldown_seconds,
        temperature=float(row.temperature),
        top_p=float(row.top_p),
        max_tokens_per_week=row.max_tokens_per_week,
        max_tokens_cap=row.max_tokens_cap,
    )
