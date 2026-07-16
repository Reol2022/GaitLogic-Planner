import type {
  FatigueState,
  InferenceBasis,
  RiskSeverity,
  RunnerStateRiskFlag,
  TrainingConsistencyState,
  TrainingPhaseState,
  VolumeTrendState,
} from "@/types/runnerState";

export type StateTone = "neutral" | "positive" | "notice" | "attention";

export interface StateDisplay {
  label: string;
  tone: StateTone;
  note: string;
}

export const volumeTrendDisplay: Record<VolumeTrendState, StateDisplay> = {
  DECREASING: { label: "下降", tone: "notice", note: "近 7 天跑量低于此前基线" },
  STABLE: { label: "稳定", tone: "positive", note: "近 7 天跑量与此前基线接近" },
  INCREASING: { label: "增长", tone: "notice", note: "近 7 天跑量高于此前基线" },
  SPIKING: { label: "明显增长", tone: "attention", note: "近 7 天跑量明显高于此前基线" },
  UNKNOWN: { label: "暂无法判断", tone: "neutral", note: "当前基线或训练数据不足" },
};

export const consistencyDisplay: Record<TrainingConsistencyState, StateDisplay> = {
  LOW: { label: "近期训练执行波动较大", tone: "notice", note: "建议结合计划与训练记录复核近期执行情况" },
  MODERATE: { label: "近期训练执行较稳定", tone: "positive", note: "当前训练执行具备一定稳定性" },
  HIGH: { label: "近期训练执行稳定", tone: "positive", note: "当前训练执行保持稳定" },
  UNKNOWN: { label: "暂无法判断", tone: "neutral", note: "当前计划或训练频率数据不足" },
};

export const fatigueDisplay: Record<FatigueState, StateDisplay> = {
  NORMAL: { label: "暂未发现明显压力信号", tone: "positive", note: "当前可用证据未显示多项训练压力信号" },
  ELEVATED: { label: "训练压力信号有所增加", tone: "notice", note: "建议结合近期体感检查恢复情况" },
  HIGH: { label: "多项训练压力信号同时出现", tone: "attention", note: "建议复核恢复情况与后续训练安排" },
  UNKNOWN: { label: "数据不足，暂无法判断", tone: "neutral", note: "当前可用训练压力证据不足" },
};

export const trainingPhaseDisplay: Record<TrainingPhaseState, StateDisplay> = {
  BASE: { label: "基础期", tone: "neutral", note: "当前训练周期设置为基础阶段" },
  BUILD: { label: "建设期", tone: "neutral", note: "当前训练周期设置为建设阶段" },
  SPECIFIC: { label: "专项期", tone: "neutral", note: "当前训练周期设置为专项阶段" },
  PEAK: { label: "峰值期", tone: "neutral", note: "当前训练周期设置为峰值阶段" },
  TAPER: { label: "减量期", tone: "neutral", note: "当前训练周期设置为减量阶段" },
  RACE: { label: "比赛期", tone: "neutral", note: "当前训练周期设置为比赛阶段" },
  RECOVERY: { label: "恢复期", tone: "neutral", note: "当前训练周期设置为恢复阶段" },
  UNKNOWN: { label: "未设置", tone: "neutral", note: "当前训练周期没有明确的结构化阶段" },
};

export const inferenceBasisLabels: Record<InferenceBasis, string> = {
  PLAN_COMPLETION: "依据计划完成情况",
  ACTIVITY_REGULARITY: "依据训练频率稳定性",
};

export const severityLabels: Record<RiskSeverity, string> = {
  ATTENTION: "需要关注",
  WARNING: "建议检查",
  INFO: "提示",
};

export const actionLabels: Record<string, string> = {
  REVIEW: "复核训练安排",
  REVIEW_RECOVERY: "检查恢复情况",
  REDUCE_LOAD: "人工评估是否降低负荷",
  ADD_RECOVERY: "人工评估恢复安排",
  COLLECT_MORE_DATA: "补充训练数据",
  MANUAL_CONFIRMATION: "人工确认",
};

export const riskTitleLabels: Record<string, string> = {
  VOLUME_SPIKE: "近期跑量明显增长",
  CONSECUTIVE_HIGH_INTENSITY_DAYS: "连续高强度训练",
  RPE_ABOVE_BASELINE: "近期主观用力感高于基线",
  RECENT_COMPLETION_DROP: "近期计划完成率下降",
  FREQUENT_HIGH_INTENSITY_SESSIONS: "近期高强度训练较多",
};

export const evidenceMetricLabels: Record<string, string> = {
  distance_7d_km: "最近 7 天跑量",
  previous_21d_weekly_average_km: "此前 21 天周均跑量",
  volume_ratio: "近期跑量相对基线比例",
  completion_rate_28d: "最近 28 天计划完成率",
  active_weeks_28d: "活跃 7 日桶数量",
  weekly_session_mean_28d: "周均训练次数",
  weekly_session_cv_28d: "周训练次数波动系数",
  volume_trend: "跑量趋势",
  average_rpe_delta: "近期 RPE 相对基线变化",
  completion_rate_drop: "计划完成率下降幅度",
  maximum_consecutive_high_intensity_days_7d: "连续高强度自然日",
  high_intensity_sessions_7d: "最近 7 天高强度次数",
};

export const signalLabels: Record<string, string> = {
  VOLUME_CHANGE: "跑量变化",
  RPE_CHANGE: "RPE 相对基线变化",
  PLAN_COMPLETION_CHANGE: "计划完成率变化",
  CONSECUTIVE_HIGH_INTENSITY_DAYS: "连续高强度训练",
  FREQUENT_HIGH_INTENSITY_SESSIONS: "高强度训练次数",
};

export const reasonCodeLabels: Record<string, string> = {
  INSUFFICIENT_DATA: "有效训练数据不足",
  INSUFFICIENT_BASELINE_DATA: "此前基线数据不足",
  INSUFFICIENT_RPE_COVERAGE: "RPE 数据覆盖不足",
  INSUFFICIENT_PLAN_DATA: "计划数据不足",
  INSUFFICIENT_FATIGUE_SIGNALS: "可用训练压力信号不足",
  TRAINING_PHASE_UNAVAILABLE: "没有结构化训练阶段",
};

export const windowLabels: Record<string, string> = {
  recent_7d: "最近 7 天",
  previous_21d: "此前 21 天",
  full_28d: "最近 28 天",
  recent_7d_vs_previous_21d: "最近 7 天对比此前 21 天",
};

export function sortRiskFlags(flags: RunnerStateRiskFlag[] = []): RunnerStateRiskFlag[] {
  const priority: Record<RiskSeverity, number> = { ATTENTION: 0, WARNING: 1, INFO: 2 };
  return [...flags].sort((a, b) => priority[a.severity] - priority[b.severity]);
}
