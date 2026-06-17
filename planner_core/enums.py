from enum import Enum


class WorkoutStatusNormalized(str, Enum):
    not_started = "not_started"
    completed_high = "completed_high"
    completed_normal = "completed_normal"
    completed_adjusted = "completed_adjusted"
    missed = "missed"
    rest = "rest"
    rest_or_cancelled = "rest_or_cancelled"
    skipped = "skipped"
    unknown = "unknown"


class WorkoutMainTypeNormalized(str, Enum):
    easy = "easy"
    easy_with_speed = "easy_with_speed"
    interval_speed = "interval_speed"
    tempo = "tempo"
    recovery = "recovery"
    long_run = "long_run"
    rest = "rest"
    mixed = "mixed"
    unknown = "unknown"


class BlockType(str, Enum):
    week = "week"
    transition = "transition"
    special = "special"


class ExcelImportStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    partial_success = "partial_success"
    failed = "failed"


class RaceDistance(str, Enum):
    m1500 = "1500m"
    m3000 = "3000m"
    m5000 = "5000m"
    m10000 = "10000m"
    half_marathon = "half_marathon"
    marathon = "marathon"


class PaceZoneCode(str, Enum):
    REC = "REC"
    E = "E"
    M = "M"
    T1 = "T1"
    T2 = "T2"
    I = "I"
    R = "R"


class FeedbackType(str, Enum):
    bug = "bug"
    suggestion = "suggestion"
    confusing = "confusing"
    training_logic = "training_logic"
    other = "other"


class AIPlanJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class AIPlanDraftStatus(str, Enum):
    draft = "draft"
    accepted = "accepted"
    rejected = "rejected"


class AIPlanIntensityStyle(str, Enum):
    conservative = "conservative"
    standard = "standard"
    aggressive = "aggressive"


class UIMode(str, Enum):
    simple = "simple"
    advanced = "advanced"


class UsageEventName(str, Enum):
    onboarding_viewed = "onboarding_viewed"
    onboarding_ai_selected = "onboarding_ai_selected"
    onboarding_excel_selected = "onboarding_excel_selected"
    onboarding_manual_selected = "onboarding_manual_selected"
    ai_plan_generate_started = "ai_plan_generate_started"
    ai_plan_generate_succeeded = "ai_plan_generate_succeeded"
    ai_plan_generate_failed = "ai_plan_generate_failed"
    ai_plan_applied = "ai_plan_applied"
    today_viewed = "today_viewed"
    workout_quick_checkin_opened = "workout_quick_checkin_opened"
    workout_log_saved = "workout_log_saved"
    calendar_viewed = "calendar_viewed"
    weekly_review_viewed = "weekly_review_viewed"
