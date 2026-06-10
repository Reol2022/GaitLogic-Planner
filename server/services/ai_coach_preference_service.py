from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import AIPlanCoachPreference
from server.schemas.ai_coach_preference import AICoachPreferenceUpdate


DEFAULT_PREFERENCE = {
    "preferred_training_systems": ["丹尼尔斯", "阈值训练", "经典周期化"],
    "intensity_conservatism": "standard",
    "key_workout_habit": "每周 1-2 次关键课，优先保证恢复质量。",
    "rest_day_strategy": "每周至少保留 1 天休息或低负荷恢复。",
    "disabled_workout_types": [],
    "double_run_policy": "cautious",
    "long_run_strategy": "长距离循序渐进，通常不超过周跑量 30%。",
    "injury_risk_policy": "出现疼痛或异常疲劳时降低强度并减少跑量。",
    "additional_notes": None,
}


def get_or_create_preference(db: Session, user_id: int) -> AIPlanCoachPreference:
    preference = db.scalar(
        select(AIPlanCoachPreference).where(AIPlanCoachPreference.user_id == user_id)
    )
    if preference is not None:
        _ensure_defaults(preference)
        return preference

    preference = AIPlanCoachPreference(user_id=user_id, **DEFAULT_PREFERENCE)
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


def _ensure_defaults(preference: AIPlanCoachPreference) -> None:
    for key, value in DEFAULT_PREFERENCE.items():
        if getattr(preference, key) is None:
            setattr(preference, key, value)


def update_preference(
    db: Session,
    user_id: int,
    payload: AICoachPreferenceUpdate,
) -> AIPlanCoachPreference:
    preference = get_or_create_preference(db, user_id)
    for key, value in payload.model_dump().items():
        setattr(preference, key, value)
    db.commit()
    db.refresh(preference)
    return preference


def preference_to_prompt_dict(preference: AIPlanCoachPreference | None) -> dict:
    if preference is None:
        return DEFAULT_PREFERENCE.copy()
    return {
        "preferred_training_systems": preference.preferred_training_systems or [],
        "intensity_conservatism": preference.intensity_conservatism,
        "key_workout_habit": preference.key_workout_habit,
        "rest_day_strategy": preference.rest_day_strategy,
        "disabled_workout_types": preference.disabled_workout_types or [],
        "double_run_policy": preference.double_run_policy,
        "long_run_strategy": preference.long_run_strategy,
        "injury_risk_policy": preference.injury_risk_policy,
        "additional_notes": preference.additional_notes,
    }
