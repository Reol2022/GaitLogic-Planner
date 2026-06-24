"""Community weekly-review thresholds.

These values support training-management prompts only. They are not medical
diagnostic thresholds and must never be presented as injury probabilities.
"""

MIN_LOGGED_WORKOUT_RATIO = 0.35
LOAD_INCREASE_WATCH_PERCENT = 15.0
LOAD_INCREASE_STRONG_PERCENT = 25.0
HIGH_RPE = 8.0
VERY_HIGH_RPE = 9.0
LOW_COMPLETION_RATE = 0.70
VERY_LOW_COMPLETION_RATE = 0.55
PAIN_WATCH_LEVEL = 4
PAIN_STRONG_LEVEL = 7
MULTIPLE_ADJUSTED_COUNT = 2
MULTIPLE_MISSED_COUNT = 2
LOW_SLEEP_HOURS = 6.0

HIGH_INTENSITY_TYPES = frozenset({"interval_speed", "tempo"})
KEY_WORKOUT_TYPES = frozenset({"interval_speed", "tempo", "long_run"})
