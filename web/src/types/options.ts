import type { WorkoutMainTypeNormalized, WorkoutStatusNormalized } from "./models";

export const mainTypeOptions: { label: string; value: WorkoutMainTypeNormalized }[] = [
  { label: "轻松跑", value: "easy" },
  { label: "轻松跑 + 速度", value: "easy_with_speed" },
  { label: "间歇 / 速度", value: "interval_speed" },
  { label: "节奏跑", value: "tempo" },
  { label: "恢复跑", value: "recovery" },
  { label: "长距离", value: "long_run" },
  { label: "休息", value: "rest" },
  { label: "混合", value: "mixed" },
  { label: "未知", value: "unknown" },
];

export const statusOptions: { label: string; value: WorkoutStatusNormalized }[] = [
  { label: "未开始", value: "not_started" },
  { label: "高质量完成", value: "completed_high" },
  { label: "正常完成", value: "completed_normal" },
  { label: "调整后完成", value: "completed_adjusted" },
  { label: "缺课", value: "missed" },
  { label: "休息", value: "rest" },
  { label: "休息 / 取消", value: "rest_or_cancelled" },
  { label: "跳过", value: "skipped" },
  { label: "未知", value: "unknown" },
];

export const blockTypeOptions = [
  { label: "标准周", value: "week" },
  { label: "过渡块", value: "transition" },
  { label: "特殊块", value: "special" },
];

export function labelFor<T extends string>(
  options: { label: string; value: T }[],
  value?: T | null,
) {
  return options.find((option) => option.value === value)?.label || value || "-";
}
