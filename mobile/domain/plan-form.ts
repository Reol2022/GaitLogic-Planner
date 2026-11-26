import { formPayload } from './runner-workspace';
import type { FormField } from './runner-workspace';
export const planFields: FormField[] = [
  { key: 'runner_level', label: '训练水平', kind: 'choice', options: ['beginner', 'intermediate', 'advanced'], labels: ['入门', '进阶', '有经验'], required: true },
  { key: 'current_weekly_mileage_km', label: '当前周跑量（km）', kind: 'number', min: 0, max: 300, required: true },
  { key: 'recent_4w_avg_mileage_km', label: '最近 4 周平均周跑量（km）', kind: 'number', min: 0, max: 300, required: true },
  { key: 'available_training_days_per_week', label: '每周可训练天数', kind: 'number', integer: true, min: 1, max: 7, required: true },
  { key: 'target_distance', label: '目标距离', kind: 'choice', options: ['1500m', '3000m', '5000m', '10000m', 'half_marathon', 'marathon'], labels: ['1500 米', '3000 米', '5 公里', '10 公里', '半马', '全马'], required: true },
  { key: 'recent_pb_distance', label: '用户自述 PB 距离（选填）', kind: 'choice', options: ['', '1500m', '3000m', '5000m', '10000m', 'half_marathon', 'marathon'], labels: ['不填写', '1500 米', '3000 米', '5 公里', '10 公里', '半马', '全马'] },
  { key: 'recent_pb_result', label: '用户自述 PB（如 01:35:00）' },
  { key: 'target_result', label: '目标成绩（如 01:30:00）' }, { key: 'target_race_name', label: '赛事名称' },
  { key: 'target_race_date', label: '赛事日期（选填）', kind: 'date' }, { key: 'plan_start_date', label: '计划开始日期', kind: 'date', required: true },
  { key: 'plan_weeks', label: '计划周数（1–16）', kind: 'number', min: 1, max: 16, integer: true, required: true },
  { key: 'intensity_style', label: '强度风格', kind: 'choice', options: ['conservative', 'standard', 'aggressive'], labels: ['保守', '标准', '积极'], required: true },
  { key: 'can_double_run', label: '是否允许双跑', kind: 'choice', options: ['false', 'true'], labels: ['不允许', '允许'], required: true },
  { key: 'fixed_rest_days', label: '固定休息日（逗号分隔，如 周一,周五）' },
  { key: 'long_run_preferred_day', label: '长距离偏好日', kind: 'choice', options: ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'], labels: ['无偏好', '周一', '周二', '周三', '周四', '周五', '周六', '周日'] },
  { key: 'excluded_workout_types', label: '不希望出现的类型（REC,E,LSD,M,T1,T2,I,R,Mixed；逗号分隔）' },
  { key: 'injury_notes', label: '伤病与注意事项' }, { key: 'training_preferences', label: '其他训练偏好' },
];
function list(value: unknown): string[] { return typeof value === 'string' ? [...new Set(value.split(/[,，]/).map(item => item.trim()).filter(Boolean))] : []; }
export function planPayload(values: Record<string, string>, daily: Record<string, string>): Record<string, unknown> {
  const payload = formPayload(planFields, values);
  payload.can_double_run = payload.can_double_run === 'true'; payload.include_pace_guidance = true; payload.use_training_context = true;
  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  const rests = list(payload.fixed_rest_days); if (rests.some(day => !days.includes(day))) throw new Error('固定休息日请使用周一至周日');
  if (7 - rests.length < Number(payload.available_training_days_per_week)) throw new Error('固定休息日与每周训练天数冲突');
  payload.fixed_rest_days = rests;
  const excluded = list(payload.excluded_workout_types); if (excluded.some(type => !['REC', 'E', 'LSD', 'M', 'T1', 'T2', 'I', 'R', 'Mixed'].includes(type))) throw new Error('禁用训练类型无效');
  payload.excluded_workout_types = excluded;
  const available: Record<string, number> = {};
  for (const day of days) if (daily[day]?.trim()) { const minutes = Number(daily[day]); if (!Number.isInteger(minutes) || minutes < 0 || minutes > 600) throw new Error(day + '可用时间须为 0–600 分钟'); available[day] = minutes; }
  payload.daily_available_minutes = available;
  if (Object.keys(available).length === 7 && days.filter(day => !rests.includes(day) && available[day] > 0).length < Number(payload.available_training_days_per_week)) throw new Error('每日可用时间与训练天数冲突');
  if ((payload.recent_pb_distance == null) !== (payload.recent_pb_result == null)) throw new Error('PB 距离和成绩需同时填写或同时留空');
  return payload;
}
export function planEnd(values: Record<string, string>): string {
  const weeks = Number(values.plan_weeks); if (!/^\d{4}-\d{2}-\d{2}$/.test(values.plan_start_date || '') || !Number.isInteger(weeks) || weeks < 1 || weeks > 16) return '';
  const date = new Date(values.plan_start_date + 'T00:00:00Z'); if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== values.plan_start_date) return '';
  date.setUTCDate(date.getUTCDate() + weeks * 7 - 1); return date.toISOString().slice(0, 10);
}
