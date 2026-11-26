export function metric(value: unknown, unit = ''): string {
  if (value === null || value === undefined || value === '') return '暂无';
  const number = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(number) ? `${Math.round(number * 100) / 100}${unit}` : '暂无';
}
export function duration(seconds: unknown): string {
  if (seconds === null || seconds === undefined || seconds === '') return '暂无';
  const value = Number(seconds); if (!Number.isFinite(value) || value < 0) return '暂无';
  const whole = Math.round(value);
  return `${Math.floor(whole / 3600)}:${String(Math.floor(whole / 60) % 60).padStart(2, '0')}:${String(whole % 60).padStart(2, '0')}`;
}
export function pace(seconds: unknown): string {
  if (seconds === null || seconds === undefined || seconds === '') return '暂无';
  const value = Math.round(Number(seconds));
  return Number.isFinite(value) && value > 0 ? `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}/km` : '暂无';
}
export function effort(value: unknown): string {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= 10 ? `${value}/10` : '暂无';
}
export function sourceLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = { GARMIN: '佳明同步', MANUAL: '手动记录', EXCEL: '表格导入', EXCEL_IMPORT: '表格导入', UNKNOWN: '来源未确认' };
  return labels[(value || '').toUpperCase()] || '其他来源';
}
export function messageStatus(value: string): string {
  const labels: Record<string, string> = { completed: '已完成', pending: '处理中', failed: '未完成', cancelled: '已取消' };
  return labels[value.toLowerCase()] || '状态待确认';
}
export function connectionStatus(value: string | null | undefined): string {
  const labels: Record<string, string> = { connected: '已连接', active: '已连接', disconnected: '尚未连接',
    reauth_required: '需要重新授权', expired: '授权已过期', failed: '连接异常', syncing: '正在同步' };
  return labels[(value || '').toLowerCase()] || '状态待确认';
}
export function dateOffset(day: string, offset: number): string {
  const date = new Date(`${day}T00:00:00Z`); date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}
export function weekStart(day: string): string {
  const weekday = new Date(`${day}T00:00:00Z`).getUTCDay();
  return dateOffset(day, -(weekday + 6) % 7);
}
