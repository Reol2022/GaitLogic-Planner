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

