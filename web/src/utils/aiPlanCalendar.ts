// Calendar dates are civil dates, not local timestamps (DST must not add a day).
const DAY = 86400000;
function dayNumber(value: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
  const [y, m, d] = value.split("-").map(Number);
  const time = Date.UTC(y, m - 1, d);
  return new Date(time).toISOString().slice(0, 10) === value ? time / DAY : NaN;
}
function dateText(day: number): string { return new Date(day * DAY).toISOString().slice(0, 10); }

export function aiPlanCalendar(startDate: string, weeks: number, raceDate?: string | null) {
  const result = { endDate: "", error: "", summary: "", recommendedWeeks: 0, lastWeekDays: 7 };
  const start = dayNumber(startDate);
  if (!Number.isFinite(start)) { result.error = "请选择有效的计划开始日期。"; return result; }
  if (!Number.isInteger(weeks) || weeks < 1 || weeks > 16) { result.error = "请输入1至16之间的整数计划周数。"; return result; }
  const nominalEnd = start + weeks * 7 - 1;
  result.endDate = dateText(nominalEnd);
  if (!raceDate) {
    result.summary = `${weeks} 个训练周，共 ${weeks * 7} 天；每周从计划开始日起连续计算7天。`;
    return result;
  }
  const race = dayNumber(raceDate);
  if (!Number.isFinite(race)) { result.error = "请选择有效的目标赛事日期。"; return result; }
  if (race < start) { result.error = "目标赛事日期早于计划开始日期，请先调整其中一个日期。"; return result; }
  const days = race - start + 1;
  const maximumWeeks = Math.ceil(days / 7);
  result.recommendedWeeks = Math.min(maximumWeeks, 16);
  if (weeks > maximumWeeks) {
    result.endDate = dateText(race);
    result.error = `从 ${startDate} 到比赛日 ${raceDate} 共 ${days} 天，最多可安排 ${maximumWeeks} 个训练周（最后一周可不足7天），当前填写 ${weeks} 周。请点击“按赛事匹配周数”或减少周数。`;
    return result;
  }
  if (race <= nominalEnd) {
    result.endDate = dateText(race);
    result.lastWeekDays = days - (weeks - 1) * 7;
    result.summary = `从 ${startDate} 到比赛日 ${raceDate} 共 ${days} 天，安排 ${weeks} 个训练周${result.lastWeekDays < 7 ? `，最后一周 ${result.lastWeekDays} 天` : ""}，计划截至比赛当天。`;
  } else {
    result.summary = `本计划共 ${weeks} 周，将于 ${result.endDate} 结束，距比赛尚有 ${race - nominalEnd} 天。本次只生成阶段计划，不覆盖完整备赛周期${maximumWeeks > 16 ? "；单次最多生成16周" : ""}。`;
  }
  return result;
}
