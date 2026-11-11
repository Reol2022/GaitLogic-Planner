"""Calendar-day plan windows, including a final partial race week."""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class PlanCalendar:
    start: date
    end: date
    weeks: int
    error: str = ''

    @property
    def week_ranges(self) -> list[dict]:
        return [dict(week=i + 1, start_date=(self.start + timedelta(days=7*i)).isoformat(),
                     end_date=min(self.start + timedelta(days=7*i+6), self.end).isoformat())
                for i in range(self.weeks) if self.start + timedelta(days=7*i) <= self.end]


def plan_calendar(start: date, weeks: int, race: date | None = None) -> PlanCalendar:
    nominal_end = start + timedelta(days=weeks * 7 - 1)
    if race is None or race >= nominal_end:
        return PlanCalendar(start, nominal_end, weeks)
    if race < start:
        return PlanCalendar(start, nominal_end, weeks, '目标赛事日期早于计划开始日期，请先调整其中一个日期。')
    days = (race - start).days + 1
    maximum = (days + 6) // 7
    if weeks > maximum:
        return PlanCalendar(start, race, weeks,
                            f'从 {start} 到比赛日 {race} 共 {days} 天，最多可安排 {maximum} 个训练周（最后一周可不足7天），当前填写 {weeks} 周，请调整计划周数。')
    return PlanCalendar(start, race, weeks)
