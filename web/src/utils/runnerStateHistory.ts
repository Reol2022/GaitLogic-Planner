import type {
  RunnerStateTimelineItem,
  RunnerStateTimelineRange,
  RunnerStateTimelineResponse,
} from "@/types/runnerState";
import { fatigueDisplay, volumeTrendDisplay } from "@/utils/runnerStateDisplay";

export const timelineRangeLabels: Record<RunnerStateTimelineRange, string> = {
  "28d": "近28天",
  "12w": "近12周",
  "6m": "近6个月",
};

export interface RunnerStateHistorySummaryCopy {
  title: string;
  recordLine: string;
  latestLine: string;
  riskDays: number;
}

export function buildHistorySummary(timeline: RunnerStateTimelineResponse): RunnerStateHistorySummaryCopy {
  const latest = timeline.items[timeline.items.length - 1];
  const rangeLabel = timelineRangeLabels[timeline.range];
  if (!latest) {
    return {
      title: `${rangeLabel}状态记录`,
      recordLine: "当前范围还没有保存记录",
      latestLine: "保存一次当前状态后，这里会开始形成训练状态时间线。",
      riskDays: 0,
    };
  }
  const volume = latest.volume_trend ? volumeTrendDisplay[latest.volume_trend].label : "暂无数据";
  const fatigue = latest.fatigue_state ? fatigueDisplay[latest.fatigue_state].label : "暂无数据";
  return {
    title: `${rangeLabel}状态记录`,
    recordLine: `已记录 ${timeline.days_with_snapshots} 天，共保存 ${timeline.total_snapshots} 次状态`,
    latestLine: `最近一次：跑量${volume}；${fatigue}`,
    riskDays: timeline.items.filter((item) => item.risk_flag_count > 0).length,
  };
}

export interface RunnerStateRiskEvent {
  snapshotId: number;
  date: string;
  flag: RunnerStateTimelineItem["risk_flags"][number];
}

export function buildRiskEvents(items: RunnerStateTimelineItem[]): RunnerStateRiskEvent[] {
  return items.flatMap((item) => item.risk_flags.map((flag) => ({
    snapshotId: item.id,
    date: item.data_cutoff_date,
    flag,
  }))).sort((a, b) => b.date.localeCompare(a.date));
}
