import type {
  CoachAgentIntent,
  CoachPlannedWorkoutStatus,
  CoachProviderStatus,
  CoachQueryStatus,
  CoachRiskLevel,
  CoachTodayDecision,
  CoachToolStatus,
} from "@/types/coachAgent";

export interface CoachDisplayValue {
  label: string;
  tone: "neutral" | "positive" | "notice" | "attention";
}

export const coachIntentDisplay: Record<CoachAgentIntent, string> = {
  TODAY_RECOMMENDATION: "今日训练建议",
  EXPLAIN_RUNNER_STATE: "解释当前状态",
  GENERAL_TRAINING_QUESTION: "一般训练问题",
};

export const coachStatusDisplay: Record<CoachQueryStatus, CoachDisplayValue> = {
  SUCCEEDED: { label: "建议已生成", tone: "positive" },
  DEGRADED: { label: "规则建议可用", tone: "notice" },
  VALIDATION_FAILED: { label: "模型回答未通过安全校验", tone: "attention" },
  REJECTED: { label: "该能力暂未开放", tone: "neutral" },
  UNAVAILABLE: { label: "AI 教练暂不可用", tone: "attention" },
};

export const coachRiskDisplay: Record<CoachRiskLevel, CoachDisplayValue> = {
  LOW: { label: "低关注", tone: "positive" },
  MODERATE: { label: "建议留意", tone: "notice" },
  HIGH: { label: "需要重点关注", tone: "attention" },
  UNKNOWN: { label: "风险信息不足", tone: "neutral" },
};

export const coachDecisionDisplay: Record<CoachTodayDecision, CoachDisplayValue> = {
  PROCEED: { label: "可以按计划执行", tone: "positive" },
  PROCEED_WITH_CAUTION: { label: "建议谨慎执行", tone: "notice" },
  CONSIDER_ADJUSTMENT: { label: "建议考虑调整", tone: "notice" },
  REST_OR_RECOVERY: { label: "建议休息或恢复", tone: "attention" },
  UNKNOWN: { label: "当前数据不足，无法确定", tone: "neutral" },
};

export const coachPlannedStatusDisplay: Record<CoachPlannedWorkoutStatus, string> = {
  PLANNED: "今日有训练计划",
  REST_DAY: "今日为计划休息日",
  NO_PLAN: "今日没有训练计划",
  CYCLE_NOT_ACTIVE: "当前没有生效的训练周期",
  UNKNOWN: "今日计划状态未知",
};

export const coachProviderStatusDisplay: Record<CoachProviderStatus, string> = {
  SUCCEEDED: "AI 解释已生成",
  DISABLED: "模型解释未启用",
  UNCONFIGURED: "模型解释未配置",
  FAILED: "模型解释暂不可用",
  NOT_CALLED: "本次未调用模型解释",
};

export const coachToolStatusDisplay: Record<CoachToolStatus, CoachDisplayValue> = {
  SUCCEEDED: { label: "已参考", tone: "positive" },
  FAILED: { label: "暂不可用", tone: "attention" },
  NOT_FOUND: { label: "没有数据", tone: "neutral" },
  NOT_ALLOWED: { label: "未获授权", tone: "attention" },
  INVALID_ARGUMENTS: { label: "参数无效", tone: "attention" },
};

const TOOL_NAMES: Record<string, string> = {
  get_runner_state: "当前跑者状态",
  get_runner_state_history: "状态历史",
  get_recent_training: "近期训练",
  get_today_workout: "今日计划",
  get_current_training_cycle: "当前训练周期",
  get_training_rules: "训练规则",
  evaluate_today_workout: "今日训练评估",
  get_training_data_quality: "训练数据质量",
};

export function coachToolName(toolName: string): string {
  return TOOL_NAMES[toolName] ?? "其他安全数据来源";
}

export function coachDataQualityLabel(value: string): string {
  const labels: Record<string, string> = {
    AVAILABLE: "数据可用",
    PARTIAL: "部分数据可用",
    UNKNOWN: "数据不足",
    NOT_FOUND: "暂无数据",
    COMPLETE: "数据完整",
    HIGH: "数据完整度高",
    MEDIUM: "数据完整度中等",
    LOW: "数据完整度较低",
    NONE: "暂无有效数据",
  };
  return labels[value] ?? "数据质量未说明";
}
