const LIMITATION_LABELS: Record<string, string> = {
  "Coverage describes available fields and is not a medical or model confidence score.": "数据完整度只表示当前字段的可用情况，不代表医疗风险或模型置信度。",
  "The current plan stores workout content as text, so structured segments were not invented.": "当前训练计划以文本保存训练内容，系统不会推测或虚构结构化训练分段。",
  intensity_distance_uses_main_workout_type: "强度距离按训练主类型统计。",
  composite_workout_intensity_segments_not_split: "复合训练暂时无法可靠拆分强度分段。",
  high_intensity_composite_segments_use_main_workout_type: "复合训练的高强度判断使用主训练类型。",
  training_phase_unavailable_no_structured_cycle_phase: "训练周期缺少结构化阶段信息，暂时无法判断当前训练阶段。",
  recovery_day_fatigue_rule_disabled_v1: "当前版本尚未启用基于无恢复日与疲劳组合的判断规则。",
  near_zero_volume_baseline_cutoff_not_defined: "当前版本尚未定义接近零跑量基线的统一判定阈值。",
  days_since_last_quality_session_unavailable: "最近一次关键训练课的日期暂无可用数据。",
  rpe_incomplete_7d: "近 7 天部分训练缺少主观用力程度（RPE）记录。",
  rpe_incomplete_28d: "近 28 天部分训练缺少主观用力程度（RPE）记录。",
};

export function limitationMessage(value: string): string {
  if (LIMITATION_LABELS[value]) return LIMITATION_LABELS[value];
  if (value.startsWith("rpe_incomplete_")) return "部分训练缺少主观用力程度（RPE）记录。";
  if (value.startsWith("heart_rate_incomplete_")) return "部分训练缺少心率记录。";
  if (value.startsWith("completion_rate_") && value.includes("no_planned_sessions")) return "当前统计窗口没有可用的计划训练数据。";
  return value;
}
