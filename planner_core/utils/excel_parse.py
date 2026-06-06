from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def parse_date(value: Any, default_year: int | None = None) -> date | None:
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    match = re.fullmatch(r"(\d{1,2})[./](\d{1,2})", text)
    if match:
        if default_year is None:
            raise ValueError("缺少年份，无法解析日期。")
        month, day = (int(match.group(1)), int(match.group(2)))
        return date(default_year, month, day)

    raise ValueError("日期格式错误。")


def parse_duration_seconds(value: Any) -> int | None:
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.hour * 3600 + value.minute * 60 + value.second
    if isinstance(value, (int, float, Decimal)):
        return int(value)

    text = str(value).strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return int(float(text))

    parts = text.split(":")
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError("时长格式错误。")


def parse_pace_seconds_per_km(value: Any) -> int | None:
    if is_blank(value):
        return None
    if isinstance(value, (int, float, Decimal)):
        return int(value)

    text = str(value).strip().lower()
    text = text.replace("/km", "").replace("公里", "").strip()
    text = text.replace("’", "'").replace("′", "'").replace("″", '"')
    text = text.replace('"', "")

    quote_match = re.fullmatch(r"(\d{1,2})'(\d{1,2})", text)
    if quote_match:
        return int(quote_match.group(1)) * 60 + int(quote_match.group(2))

    colon_match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", text)
    if colon_match:
        return int(colon_match.group(1)) * 60 + int(colon_match.group(2))

    if re.fullmatch(r"\d+(\.\d+)?", text):
        return int(float(text))

    raise ValueError("配速格式错误。")


def parse_decimal(value: Any) -> Decimal | None:
    if is_blank(value):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip().lower()
    text = text.replace("公里", "").replace("km", "").replace("%", "").strip()
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("数字格式错误。") from exc


def normalize_workout_main_type(value: Any) -> WorkoutMainTypeNormalized:
    if is_blank(value):
        return WorkoutMainTypeNormalized.unknown
    normalized = str(value).strip().upper()
    mapping = {
        "REC": WorkoutMainTypeNormalized.recovery,
        "E": WorkoutMainTypeNormalized.easy,
        "E+R": WorkoutMainTypeNormalized.easy_with_speed,
        "LSD": WorkoutMainTypeNormalized.long_run,
        "M": WorkoutMainTypeNormalized.mixed,
        "T": WorkoutMainTypeNormalized.tempo,
        "T1": WorkoutMainTypeNormalized.tempo,
        "T2": WorkoutMainTypeNormalized.tempo,
        "I": WorkoutMainTypeNormalized.interval_speed,
        "I/R": WorkoutMainTypeNormalized.interval_speed,
        "R": WorkoutMainTypeNormalized.interval_speed,
        "REST": WorkoutMainTypeNormalized.rest,
        "MIXED": WorkoutMainTypeNormalized.mixed,
    }
    return mapping.get(normalized, WorkoutMainTypeNormalized.unknown)


def normalize_workout_status(value: Any) -> WorkoutStatusNormalized:
    if is_blank(value):
        return WorkoutStatusNormalized.not_started
    normalized = str(value).strip()
    mapping = {
        "高质量完成": WorkoutStatusNormalized.completed_high,
        "一般完成": WorkoutStatusNormalized.completed_normal,
        "正常完成": WorkoutStatusNormalized.completed_normal,
        "降级完成": WorkoutStatusNormalized.completed_adjusted,
        "没完成": WorkoutStatusNormalized.missed,
        "未完成": WorkoutStatusNormalized.missed,
        "休息": WorkoutStatusNormalized.rest,
        "取消/休息": WorkoutStatusNormalized.rest_or_cancelled,
        "跳过": WorkoutStatusNormalized.skipped,
    }
    return mapping.get(normalized, WorkoutStatusNormalized.unknown)
