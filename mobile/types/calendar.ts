export interface CalendarDay {
  date: string
  weekday?: string
  planned_workout_id: number | null
  planned_content: string | null
  planned_distance_km: number | string | null
  main_type: string | null
  status_normalized?: string
  actual_distance_km?: number | string | null
  avg_pace_seconds_per_km?: number | null
  avg_heart_rate?: number | null
  rpe?: number | null
  review_note?: string | null
  has_garmin_activity?: boolean
}

export interface CalendarSummary {
  planned_distance_km: number | string
  actual_distance_km: number | string
  completion_rate: number | string
  completed_days: number
  missed_days: number
}

export interface TrainingCalendar {
  month: string
  days: CalendarDay[]
  summary?: CalendarSummary
}
