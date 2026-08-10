"""Versioned conservative product heuristics, not medical thresholds."""

WEEKLY_FACTS_VERSION = "weekly-facts-1.0.0"
WEEKLY_RULES_VERSION = "weekly-review-rules-1.0.0"

DISTANCE_UNDER_RATIO = 0.80
DISTANCE_ON_TRACK_MIN = 0.90
DISTANCE_ON_TRACK_MAX = 1.10
DISTANCE_OVER_RATIO = 1.20

EASY_TYPES = frozenset({"easy", "easy_with_speed", "recovery"})
MODERATE_TYPES = frozenset({"long_run", "mixed"})
HARD_TYPES = frozenset({"interval_speed", "tempo"})
KEY_TYPES = frozenset({"interval_speed", "tempo", "long_run"})
COMPLETED_STATUSES = frozenset(
    {"completed_high", "completed_normal", "completed_adjusted"}
)
CANCELLED_STATUSES = frozenset({"rest_or_cancelled", "skipped"})
