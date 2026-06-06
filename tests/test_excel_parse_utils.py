from datetime import date, datetime
from decimal import Decimal

from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized
from planner_core.utils.excel_parse import (
    normalize_workout_main_type,
    normalize_workout_status,
    parse_date,
    parse_decimal,
    parse_duration_seconds,
    parse_pace_seconds_per_km,
)


def test_parse_date_supported_formats():
    assert parse_date(date(2026, 6, 1)) == date(2026, 6, 1)
    assert parse_date(datetime(2026, 6, 1, 8, 0)) == date(2026, 6, 1)
    assert parse_date("2026-06-01") == date(2026, 6, 1)
    assert parse_date("2026/06/01") == date(2026, 6, 1)
    assert parse_date("06.01", default_year=2026) == date(2026, 6, 1)


def test_parse_duration_seconds_supported_formats():
    assert parse_duration_seconds(3000) == 3000
    assert parse_duration_seconds("3000") == 3000
    assert parse_duration_seconds("50:00") == 3000
    assert parse_duration_seconds("01:23:45") == 5025


def test_parse_pace_seconds_per_km_supported_formats():
    assert parse_pace_seconds_per_km(290) == 290
    assert parse_pace_seconds_per_km("4:50") == 290
    assert parse_pace_seconds_per_km("04:50") == 290
    assert parse_pace_seconds_per_km("4'50\"") == 290
    assert parse_pace_seconds_per_km("4:50/km") == 290


def test_parse_decimal_supported_formats():
    assert parse_decimal(None) is None
    assert parse_decimal("") is None
    assert parse_decimal(10) == Decimal("10")
    assert parse_decimal("10.5") == Decimal("10.5")
    assert parse_decimal("10km") == Decimal("10")


def test_normalize_workout_main_type():
    assert normalize_workout_main_type("REC") == WorkoutMainTypeNormalized.recovery
    assert normalize_workout_main_type("E+R") == WorkoutMainTypeNormalized.easy_with_speed
    assert normalize_workout_main_type("LSD") == WorkoutMainTypeNormalized.long_run
    assert normalize_workout_main_type("M") == WorkoutMainTypeNormalized.mixed
    assert normalize_workout_main_type("T2") == WorkoutMainTypeNormalized.tempo
    assert normalize_workout_main_type("I/R") == WorkoutMainTypeNormalized.interval_speed
    assert normalize_workout_main_type("Rest") == WorkoutMainTypeNormalized.rest
    assert normalize_workout_main_type("???") == WorkoutMainTypeNormalized.unknown


def test_normalize_workout_status():
    assert normalize_workout_status("") == WorkoutStatusNormalized.not_started
    assert normalize_workout_status("高质量完成") == WorkoutStatusNormalized.completed_high
    assert normalize_workout_status("一般完成") == WorkoutStatusNormalized.completed_normal
    assert normalize_workout_status("降级完成") == WorkoutStatusNormalized.completed_adjusted
    assert normalize_workout_status("没完成") == WorkoutStatusNormalized.missed
    assert normalize_workout_status("取消/休息") == WorkoutStatusNormalized.rest_or_cancelled
    assert normalize_workout_status("未知文本") == WorkoutStatusNormalized.unknown
