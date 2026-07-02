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


class AuthEntryMode(str, Enum):
    standalone = "standalone"
    modal = "modal"


class WeeklyReviewStatus(str, Enum):
    pending = "pending"
    generating = "generating"
    success = "success"
    failed = "failed"


class TrainingStatus(str, Enum):
    insufficient_data = "insufficient_data"
    normal = "normal"
    watch = "watch"
    reduce_load = "reduce_load"


class ReadinessDataQuality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PainTrend(str, Enum):
    improving = "improving"
    stable = "stable"
    worsening = "worsening"
    unknown = "unknown"


class RecoveryCheckinSource(str, Enum):
    manual = "manual"


class PainScaleVersion(str, Enum):
    normalized_0_10 = "normalized_0_10"
    native_0_10 = "native_0_10"


class FeatureKey(str, Enum):
    training_readiness = "training_readiness"
    workout_import = "workout_import"


class ReadinessRecommendationAction(str, Enum):
    maintain_plan = "maintain_plan"
    monitor = "monitor"
    remove_optional_volume = "remove_optional_volume"
    reduce_easy_volume = "reduce_easy_volume"
    reduce_quality_volume = "reduce_quality_volume"
    replace_quality_with_easy = "replace_quality_with_easy"
    add_recovery_day = "add_recovery_day"
    seek_professional_evaluation = "seek_professional_evaluation"


class PlanAdjustmentDraftStatus(str, Enum):
    uploaded = "uploaded"
    parsed = "parsed"
    validation_failed = "validation_failed"
    ready = "ready"
    conflict = "conflict"
    draft = "draft"
    partially_applied = "partially_applied"
    applied = "applied"
    cancelled = "cancelled"
    expired = "expired"
    rejected = "rejected"
    invalid = "invalid"


class PlanAdjustmentAction(str, Enum):
    keep = "keep"
    reduce = "reduce"
    replace = "replace"
    rest = "rest"


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
    weekly_review_summary_viewed = "weekly_review_summary_viewed"
    weekly_review_generate_started = "weekly_review_generate_started"
    weekly_review_generate_succeeded = "weekly_review_generate_succeeded"
    weekly_review_generate_failed = "weekly_review_generate_failed"
    weekly_review_regenerated = "weekly_review_regenerated"
    adjustment_draft_viewed = "adjustment_draft_viewed"
    adjustment_item_selected = "adjustment_item_selected"
    adjustment_item_edited = "adjustment_item_edited"
    adjustment_draft_applied = "adjustment_draft_applied"
    adjustment_draft_rejected = "adjustment_draft_rejected"
    recovery_checkin_viewed = "recovery_checkin_viewed"
    recovery_checkin_saved = "recovery_checkin_saved"
    recovery_checkin_updated = "recovery_checkin_updated"
    recovery_checkin_deleted = "recovery_checkin_deleted"
    readiness_card_viewed = "readiness_card_viewed"
    readiness_detail_viewed = "readiness_detail_viewed"
    readiness_recalculated = "readiness_recalculated"
    load_trend_viewed = "load_trend_viewed"
    recovery_trend_viewed = "recovery_trend_viewed"
    reduce_load_suggestion_viewed = "reduce_load_suggestion_viewed"
    readiness_adjustment_draft_created = "readiness_adjustment_draft_created"
    workout_import_page_viewed = "workout_import_page_viewed"
    workout_import_file_selected = "workout_import_file_selected"
    workout_import_json_submitted = "workout_import_json_submitted"
    workout_import_parsed = "workout_import_parsed"
    workout_import_validation_failed = "workout_import_validation_failed"
    workout_import_preview_viewed = "workout_import_preview_viewed"
    workout_import_item_edited = "workout_import_item_edited"
    workout_import_applied = "workout_import_applied"
    workout_import_cancelled = "workout_import_cancelled"
    workout_import_subjective_data_prompt_viewed = "workout_import_subjective_data_prompt_viewed"
