from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from server.agent.training_date_range import parse_race_context, parse_training_date_range


NOW = datetime(2026, 10, 26, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


@pytest.mark.parametrize(
    ("message", "start", "end", "kind"),
    [
        ("读取本月训练并分析", "2026-10-01", "2026-10-26", "CURRENT_CALENDAR_MONTH"),
        ("复盘上个月训练", "2026-09-01", "2026-09-30", "PREVIOUS_CALENDAR_MONTH"),
        ("分析本周训练", "2026-10-26", "2026-10-26", "CURRENT_CALENDAR_WEEK"),
        ("看看最近7天", "2026-10-20", "2026-10-26", "ROLLING_7_DAYS"),
        ("分析最近28天", "2026-09-29", "2026-10-26", "ROLLING_28_DAYS"),
    ],
)
def test_resolves_user_time_range_without_substituting_rolling_28_days(message, start, end, kind) -> None:
    result = parse_training_date_range(message, NOW)
    assert result.start_date.isoformat() == start
    assert result.end_date.isoformat() == end
    assert result.kind == kind


def test_recognises_relative_and_explicit_race_dates_without_persisting_them() -> None:
    relative = parse_race_context("两周后有半马比赛", NOW)
    conversational = parse_race_context("还有两周半马比赛，我该如何调整", NOW)
    explicit = parse_race_context("11月15日参加半马", NOW)
    assert relative is not None and relative.race_date.isoformat() == "2026-11-09"
    assert relative.source == "USER_RELATIVE_DATE"
    assert conversational is not None and conversational.race_date == relative.race_date
    assert explicit is not None and explicit.race_date.isoformat() == "2026-11-15"
