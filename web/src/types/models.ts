export type WorkoutStatusNormalized =
  | "not_started"
  | "completed_high"
  | "completed_normal"
  | "completed_adjusted"
  | "missed"
  | "rest"
  | "rest_or_cancelled"
  | "skipped"
  | "unknown";

export type WorkoutMainTypeNormalized =
  | "easy"
  | "easy_with_speed"
  | "interval_speed"
  | "tempo"
  | "recovery"
  | "long_run"
  | "rest"
  | "mixed"
  | "unknown";

export type BlockType = "week" | "transition" | "special";

export interface TrainingCycle {
  id: number;
  name: string;
  goal?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  target_race_name?: string | null;
  target_race_date?: string | null;
  target_result?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export type TrainingCyclePayload = Omit<TrainingCycle, "id" | "created_at" | "updated_at">;

export interface TrainingBlock {
  id: number;
  cycle_id: number;
  block_name: string;
  block_type: BlockType;
  week_index?: number | null;
  sort_order: number;
  date_range_text?: string | null;
  target_text?: string | null;
  target_distance_min_km?: number | string | null;
  target_distance_max_km?: number | string | null;
  planned_distance_km?: number | string | null;
  start_date?: string | null;
  end_date?: string | null;
  phase_name?: string | null;
  focus?: string | null;
  created_at: string;
  updated_at: string;
}

export type TrainingBlockPayload = Omit<TrainingBlock, "id" | "created_at" | "updated_at">;

export interface WorkoutLog {
  id: number;
  planned_workout_id: number;
  status_raw?: string | null;
  status_normalized: WorkoutStatusNormalized;
  actual_distance_km?: number | string | null;
  actual_duration_seconds?: number | null;
  avg_pace_seconds_per_km?: number | null;
  avg_heart_rate?: number | null;
  rpe?: number | null;
  i_effective_km?: number | string | null;
  t1_effective_km?: number | string | null;
  t2_effective_km?: number | string | null;
  m_effective_km?: number | string | null;
  r_effective_km?: number | string | null;
  sleep_hours?: number | string | null;
  hrv?: number | null;
  morning_heart_rate?: number | null;
  weight_kg?: number | string | null;
  leg_feeling?: string | null;
  pain_location?: string | null;
  pain_level?: number | null;
  main_session_data?: string | null;
  review_note?: string | null;
  tomorrow_adjustment?: string | null;
  alert_message?: string | null;
  completion_rate?: number | string | null;
  created_at: string;
  updated_at: string;
}

export type WorkoutLogPayload = Partial<
  Omit<WorkoutLog, "id" | "planned_workout_id" | "created_at" | "updated_at">
>;

export interface PlannedWorkout {
  id: number;
  cycle_id: number;
  block_id: number;
  workout_date?: string | null;
  date_text?: string | null;
  weekday?: string | null;
  month_text?: string | null;
  phase_name?: string | null;
  planned_content: string;
  focus_note?: string | null;
  planned_distance_km?: number | string | null;
  main_type_raw?: string | null;
  main_type_normalized: WorkoutMainTypeNormalized;
  source_sheet?: string | null;
  source_row?: number | null;
  sort_order: number;
  workout_log?: WorkoutLog | null;
  created_at: string;
  updated_at: string;
}

export type PlannedWorkoutPayload = Omit<
  PlannedWorkout,
  "id" | "workout_log" | "created_at" | "updated_at"
>;

export interface PaceRule {
  id: number;
  code: string;
  name: string;
  target_pace_text?: string | null;
  physiological_purpose?: string | null;
  note?: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export type PaceRulePayload = Omit<PaceRule, "id" | "created_at" | "updated_at">;

export type RaceDistance =
  | "1500m"
  | "3000m"
  | "5000m"
  | "10000m"
  | "half_marathon"
  | "marathon";

export type PaceZoneCode = "REC" | "E" | "M" | "T1" | "T2" | "I" | "R";

export interface PaceZone {
  id?: number | null;
  zone_code: PaceZoneCode;
  zone_name: string;
  pace_min_seconds_per_km: number;
  pace_max_seconds_per_km: number;
  target_pace_text: string;
  description?: string | null;
  sort_order?: number | null;
}

export interface PaceCalculationPayload {
  race_distance: RaceDistance;
  race_result: string;
  age?: number | null;
  sex?: RunnerSex;
}

export interface AgeGradingReference {
  age: number;
  sex: RunnerSex;
  source: string;
  age_factor: number;
  age_standard_seconds: number;
  age_graded_seconds: number;
  age_grade_percent: number;
  level_label: string;
  note: string;
}

export interface PaceCalculationResult {
  race_distance: RaceDistance;
  race_result_seconds: number;
  vdot: number;
  zones: PaceZone[];
  age_reference?: string | null;
  age_grading?: AgeGradingReference | null;
}

export interface PaceProfile {
  id: number;
  name: string;
  race_distance: RaceDistance;
  race_result_seconds: number;
  vdot: number | string;
  algorithm_version: string;
  created_at: string;
  updated_at: string;
  zones?: PaceZone[];
}

export interface PaceProfileCreatePayload extends PaceCalculationPayload {
  name: string;
}

export type RunnerSex = "male" | "female" | "unknown";

export interface TrainingCalendarDay {
  date: string;
  weekday: string;
  planned_workout_id?: number | null;
  planned_content?: string | null;
  planned_distance_km?: number | string | null;
  main_type?: WorkoutMainTypeNormalized | null;
  status_normalized: WorkoutStatusNormalized;
  actual_distance_km?: number | string | null;
  avg_pace_seconds_per_km?: number | null;
  avg_heart_rate?: number | null;
  rpe?: number | null;
  review_note?: string | null;
  completion_rate?: number | string | null;
}

export interface TrainingCalendarSummary {
  planned_distance_km: number | string;
  actual_distance_km: number | string;
  completion_rate: number | string;
  completed_days: number;
  missed_days: number;
}

export interface TrainingCalendarResult {
  month: string;
  days: TrainingCalendarDay[];
  summary: TrainingCalendarSummary;
}

export interface DashboardSummary {
  planned_distance_km: number | string;
  actual_distance_km: number | string;
  completion_rate: number | string;
  workout_count: number;
  completed_count: number;
  missed_count: number;
  avg_rpe?: number | string | null;
  max_pain_level?: number | null;
  main_type_distribution: Record<string, number>;
}

export interface BlockStats {
  planned_distance_km: number | string;
  actual_distance_km: number | string;
  completion_rate: number | string;
  i_effective_km: number | string;
  t1_effective_km: number | string;
  t2_effective_km: number | string;
  m_effective_km: number | string;
  r_effective_km: number | string;
  avg_rpe?: number | string | null;
  avg_weight_kg?: number | string | null;
  max_pain_level?: number | null;
}

export interface UserAccount {
  id: number;
  username: string;
  email?: string | null;
  nickname?: string | null;
  avatar_url?: string | null;
  role: string;
  ui_mode: "simple" | "advanced" | string;
  status: string;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserRegisterPayload {
  username: string;
  password: string;
  email?: string | null;
  nickname?: string | null;
}

export interface UserLoginPayload {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface ExcelImportErrorItem {
  sheet: string;
  row: number;
  message: string;
}

export interface ExcelImportResult {
  status: "success" | "partial_success" | "failed" | string;
  message: string;
  total_count: number;
  success_count: number;
  failed_count: number;
  errors: ExcelImportErrorItem[];
}

export type FeedbackType = "bug" | "suggestion" | "confusing" | "training_logic" | "other";

export interface FeedbackPayload {
  feedback_type: FeedbackType;
  page_url?: string | null;
  content: string;
  contact?: string | null;
}

export interface FeedbackItem extends FeedbackPayload {
  id: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export type AIPlanIntensityStyle = "conservative" | "standard" | "aggressive";
export type AIPlanDraftStatus = "draft" | "accepted" | "rejected";
export type AIPlanExportFormat =
  | "xlsx"
  | "csv"
  | "markdown"
  | "json"
  | "ics"
  | "garmin_csv"
  | "coros_csv"
  | "device_csv";

export interface AIPlanGeneratePayload {
  runner_level: string;
  recent_pb_distance?: RaceDistance | null;
  recent_pb_result?: string | null;
  current_weekly_mileage_km: number;
  recent_4w_avg_mileage_km: number;
  available_training_days_per_week: number;
  can_double_run: boolean;
  fixed_rest_days: string[];
  injury_notes?: string | null;
  training_preferences?: string | null;
  target_race_name?: string | null;
  target_race_date?: string | null;
  target_distance: RaceDistance;
  target_result?: string | null;
  plan_start_date: string;
  plan_weeks: number;
  intensity_style: AIPlanIntensityStyle;
  include_pace_guidance: boolean;
}

export interface AIPlanDraftWorkout {
  id?: number | null;
  workout_date: string;
  weekday?: string | null;
  block_name?: string | null;
  phase_name?: string | null;
  planned_content: string;
  focus_note?: string | null;
  planned_distance_km?: number | string | null;
  main_type_raw?: string | null;
  main_type_normalized: WorkoutMainTypeNormalized;
  target_pace_text?: string | null;
  sort_order: number;
}

export interface AIPlanDraft {
  id: number;
  job_id: number;
  title: string;
  goal?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  target_race_name?: string | null;
  target_race_date?: string | null;
  target_result?: string | null;
  summary?: string | null;
  risk_notes?: string[] | null;
  status: AIPlanDraftStatus;
  created_at: string;
  updated_at: string;
  workouts?: AIPlanDraftWorkout[];
}

export interface AIPlanGenerateResult {
  job_id: number;
  draft_id: number;
  title: string;
  goal?: string | null;
  summary?: string | null;
  risk_notes?: string[] | null;
  workouts: AIPlanDraftWorkout[];
}

export interface AIPlanQuota {
  model_name: string;
  daily_limit: number;
  used_count: number;
  remaining_count: number;
  last_generated_at?: string | null;
  cooldown_seconds: number;
  can_generate: boolean;
}

export type AICoachIntensityConservatism = "conservative" | "standard" | "aggressive" | "custom";
export type AICoachDoubleRunPolicy = "never" | "cautious" | "allowed";

export interface AICoachPreference {
  id?: number | null;
  preferred_training_systems: string[];
  intensity_conservatism: AICoachIntensityConservatism | string;
  key_workout_habit?: string | null;
  rest_day_strategy?: string | null;
  disabled_workout_types: string[];
  double_run_policy: AICoachDoubleRunPolicy | string;
  long_run_strategy?: string | null;
  injury_risk_policy?: string | null;
  additional_notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type AICoachPreferencePayload = Omit<AICoachPreference, "id" | "created_at" | "updated_at">;

export interface AdminAISettings {
  id?: number | null;
  provider: "deepseek" | "openai" | "custom" | string;
  base_url: string;
  model_name: string;
  timeout_seconds: number;
  ai_plan_daily_limit: number;
  ai_plan_cooldown_seconds: number;
  temperature: number;
  top_p: number;
  max_tokens_per_week: number;
  max_tokens_cap: number;
  has_api_key: boolean;
  api_key_preview?: string | null;
  updated_at?: string | null;
}

export interface AdminAISettingsPayload {
  provider: "deepseek" | "openai" | "custom" | string;
  base_url: string;
  model_name: string;
  api_key?: string | null;
  timeout_seconds: number;
  ai_plan_daily_limit: number;
  ai_plan_cooldown_seconds: number;
  temperature: number;
  top_p: number;
  max_tokens_per_week: number;
  max_tokens_cap: number;
}

export interface AdminUser {
  id: number;
  username: string;
  email?: string | null;
  nickname?: string | null;
  role: "user" | "admin" | string;
  status: "active" | "disabled" | string;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminUserUpdatePayload {
  email?: string | null;
  nickname?: string | null;
  role: "user" | "admin";
  status: "active" | "disabled";
}
