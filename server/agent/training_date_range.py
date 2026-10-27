from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class TrainingDateRange:
    start_date: date
    end_date: date
    kind: str
    label: str

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True)
class RaceContext:
    race_date: date
    source: str


def _previous_month(today: date) -> tuple[date, date]:
    last_day = today.replace(day=1) - timedelta(days=1)
    return last_day.replace(day=1), last_day


def parse_training_date_range(message: str, current_time: datetime) -> TrainingDateRange:
    """Resolve explicit runner language into one bounded local-calendar range."""

    text = message.strip().lower()
    today = current_time.date()
    if any(marker in text for marker in ("上个月", "上月", "last month")):
        start, end = _previous_month(today)
        return TrainingDateRange(start, end, "PREVIOUS_CALENDAR_MONTH", "上一个完整自然月")
    if any(marker in text for marker in ("本月", "这个月", "this month")):
        return TrainingDateRange(today.replace(day=1), today, "CURRENT_CALENDAR_MONTH", "本月截至当前日期")
    if any(marker in text for marker in ("本周", "这周", "this week")):
        return TrainingDateRange(today - timedelta(days=today.weekday()), today, "CURRENT_CALENDAR_WEEK", "本周截至当前日期")
    if any(marker in text for marker in ("最近7天", "近7天", "过去7天", "last 7 days")):
        return TrainingDateRange(today - timedelta(days=6), today, "ROLLING_7_DAYS", "最近 7 天")
    if any(marker in text for marker in ("最近28天", "近28天", "最近四周", "近四周", "last 28 days")):
        return TrainingDateRange(today - timedelta(days=27), today, "ROLLING_28_DAYS", "最近 28 天")
    return TrainingDateRange(today - timedelta(days=27), today, "ROLLING_28_DAYS", "最近 28 天")


def parse_race_context(message: str, current_time: datetime) -> RaceContext | None:
    text = message.strip().lower()
    if not any(marker in text for marker in ("比赛", "半马", "马拉松", "race")):
        return None
    today = current_time.date()
    relative = re.search(r"(?:还有|剩余)?\s*(\d{1,2}|一|两|二|三|四|五|六|七|八)\s*周(?:后)?", text)
    if relative:
        raw = relative.group(1)
        weeks = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}.get(raw, int(raw) if raw.isdigit() else 0)
        if 1 <= weeks <= 8:
            return RaceContext(today + timedelta(weeks=weeks), "USER_RELATIVE_DATE")
    explicit = re.search(r"(?:(20\d{2})[年/-])?(\d{1,2})[月/-](\d{1,2})[日号]?", text)
    if explicit:
        year = int(explicit.group(1)) if explicit.group(1) else today.year
        month, day = int(explicit.group(2)), int(explicit.group(3))
        try:
            target = date(year, month, day)
            if explicit.group(1) is None and target < today:
                target = target.replace(year=year + 1)
        except ValueError:
            return None
        if today <= target <= today + timedelta(days=366):
            return RaceContext(target, "USER_EXPLICIT_DATE")
    return None
