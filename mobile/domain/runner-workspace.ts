/** Client-side allowlist; ownership, locks and business validation remain server-side. */
export interface FormField { key: string; label: string; kind?: 'number' | 'date' | 'text' | 'choice'; required?: boolean; min?: number; max?: number; integer?: boolean; options?: string[]; labels?: string[] }
export interface ResourceDefinition { key: string; title: string; endpoint: string; titleKey: string; fields: FormField[] }
const field = (key: string, label: string, kind: FormField['kind'] = 'text', required = false): FormField => ({ key, label, kind, required });
export const workoutTypes = ['easy', 'easy_with_speed', 'interval_speed', 'tempo', 'recovery', 'long_run', 'rest', 'mixed', 'unknown'];
export const workoutTypeLabels = ['轻松跑', '轻松跑加速', '间歇速度', '节奏跑', '恢复跑', '长距离', '休息', '混合训练', '未分类'];
export const resources: ResourceDefinition[] = [
  { key: 'pace-rules', title: '配速规则', endpoint: '/pace-rules', titleKey: 'name', fields: [field('code', '代码', 'text', true), field('name', '名称', 'text', true), field('target_pace_text', '目标配速'), field('physiological_purpose', '训练目的'), field('note', '说明'), { key: 'sort_order', label: '排序', kind: 'number', integer: true, min: 0, required: true }] },
  { key: 'cycles', title: '训练周期', endpoint: '/training-cycles', titleKey: 'name', fields: [field('name', '周期名称', 'text', true), field('goal', '训练目标'), field('start_date', '开始日期', 'date'), field('end_date', '结束日期', 'date'), field('target_race_name', '目标赛事'), field('target_race_date', '赛事日期', 'date'), field('target_result', '目标成绩'), field('description', '周期说明')] },
  { key: 'blocks', title: '训练块', endpoint: '/training-blocks', titleKey: 'block_name', fields: [field('block_name', '训练块名称', 'text', true), { key: 'block_type', label: '类型', kind: 'choice', options: ['week', 'transition', 'special'], labels: ['周训练块', '过渡块', '专项块'], required: true }, { key: 'sort_order', label: '排序', kind: 'number', integer: true, min: 0, required: true }, { key: 'week_index', label: '周序号', kind: 'number', integer: true, min: 1 }, field('start_date', '开始日期', 'date'), field('end_date', '结束日期', 'date'), field('phase_name', '阶段'), field('focus', '训练重点'), field('target_text', '目标说明'), { key: 'planned_distance_km', label: '计划跑量（km）', kind: 'number', min: 0 }] },
  { key: 'workouts', title: '每日计划', endpoint: '/planned-workouts', titleKey: 'planned_content', fields: [field('workout_date', '训练日期', 'date', true), field('planned_content', '训练内容', 'text', true), { key: 'main_type_normalized', label: '计划类型', kind: 'choice', options: workoutTypes, labels: workoutTypeLabels, required: true }, { key: 'planned_distance_km', label: '计划距离（km）', kind: 'number', min: 0 }, field('target_pace_text', '目标配速'), field('focus_note', '注意事项'), { key: 'session_index', label: '当日第几次训练', kind: 'number', integer: true, min: 1, required: true }, { key: 'sort_order', label: '排序', kind: 'number', integer: true, min: 0, required: true }] },
];
export function resourceFor(key: string): ResourceDefinition {
  const result = resources.find(item => item.key === key);
  if (!result) throw new Error('不支持的训练页面');
  return result;
}
export function positiveId(value: unknown): number {
  const text = String(value ?? '');
  if (!/^[1-9]\d*$/.test(text) || !Number.isSafeInteger(Number(text))) throw new Error('记录编号无效，请从列表重新进入');
  return Number(text);
}
export function valuesFor(fields: FormField[], record: Record<string, unknown>): Record<string, string> {
  const output: Record<string, string> = {};
  for (const item of fields) output[item.key] = record[item.key] == null ? '' : String(record[item.key]);
  return output;
}
export function formPayload(fields: FormField[], values: Record<string, string>): Record<string, unknown> {
  const output: Record<string, unknown> = {};
  for (const item of fields) {
    const text = (values[item.key] ?? '').trim();
    if (!text) { if (item.required) throw new Error('请填写' + item.label); output[item.key] = null; continue; }
    if (item.kind === 'number') {
      const number = Number(text);
      if (!Number.isFinite(number) || (item.integer && !Number.isInteger(number)) || (item.min != null && number < item.min) || (item.max != null && number > item.max)) throw new Error(item.label + '超出允许范围');
      output[item.key] = number;
    } else if (item.kind === 'date') {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(text) || !Number.isFinite(Date.parse(text + 'T00:00:00Z')) || new Date(text + 'T00:00:00Z').toISOString().slice(0, 10) !== text) throw new Error(item.label + '无效');
      output[item.key] = text;
    } else { if (item.options && !item.options.includes(text)) throw new Error(item.label + '无效'); output[item.key] = text; }
  }
  const start = output.start_date, end = output.end_date;
  if (typeof start === 'string' && typeof end === 'string' && end < start) throw new Error('结束日期不能早于开始日期');
  return output;
}
export function changedPayload(fields: FormField[], values: Record<string, string>, original: Record<string, string>): Record<string, unknown> {
  const all = formPayload(fields, values), changed: Record<string, unknown> = {};
  for (const item of fields) if (values[item.key] !== original[item.key]) changed[item.key] = all[item.key];
  return changed;
}
