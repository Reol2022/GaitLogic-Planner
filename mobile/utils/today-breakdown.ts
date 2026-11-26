export interface ActivityPart {
  activity_ref: string
  date: string
  start_time_local?: string
  distance_km: number | null
  duration_seconds: number | null
  average_pace_seconds_per_km?: number | null
}
export interface TrainingSegment {
  index: number
  role: string
  distance_m: number | null
  duration_seconds: number | null
  average_pace_seconds_per_km?: number | null
}
export interface TodayDetail {
  activities: ActivityPart[]
  activities_complete?: boolean
  selected_activity?: ActivityPart | null
  normalized_segments?: TrainingSegment[]
  normalized_structure_complete?: boolean
  session_confirmation?: { status?: string; activity_roles?: { activity_ref: string; role: string }[] }
}

export function roleLabel(role?: string): string {
  const labels: Record<string, string> = { warmup: '热身', warm_up: '热身', main: '主训练', active: '主训练', recovery: '恢复', cooldown: '放松', cool_down: '放松' }
  return labels[(role || '').toLowerCase()] || ''
}

export function activityLabel(detail: TodayDetail, ref: string, index: number): string {
  if (detail.session_confirmation?.status === 'CONFIRMED') {
    const label = roleLabel(detail.session_confirmation.activity_roles?.find(item => item.activity_ref === ref)?.role)
    if (label) return label + ' · 已确认'
  }
  return '活动 ' + (index + 1)
}

export function activityTime(value?: string): string {
  return value?.match(/[T ](\d{2}:\d{2})/)?.[1] ?? ''
}
