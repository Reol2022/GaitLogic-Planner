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
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  status: "draft" | "active" | "completed" | "archived" | string;
  activated_at?: string | null;
  completed_at?: string | null;
  superseded_by_cycle_id?: number | null;
  target_race_name?: string | null;
  target_race_date?: string | null;
  target_result?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export type TrainingCyclePayload = Omit<
  TrainingCycle,
  "id" | "status" | "actual_start_date" | "actual_end_date" | "activated_at" | "completed_at" | "superseded_by_cycle_id" | "created_at" | "updated_at"
>;

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
  planned_workout_id?: number | null;
  status_raw?: string | null;
  status_normalized: WorkoutStatusNormalized;
  actual_distance_km?: number | string | null;
  actual_duration_seconds?: number | null;
  moving_time_seconds?: number | null;
  elapsed_time_seconds?: number | null;
  avg_pace_seconds_per_km?: number | null;
  avg_heart_rate?: number | null;
  max_heart_rate?: number | null;
  average_cadence_spm?: number | null;
  max_cadence_spm?: number | null;
  elevation_gain_m?: number | null;
  calories_kcal?: number | null;
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
  pain_scale_version?: "normalized_0_10" | "native_0_10";
  main_session_data?: string | null;
  review_note?: string | null;
  tomorrow_adjustment?: string | null;
  alert_message?: string | null;
  completion_rate?: number | string | null;
  activity_date?: string | null;
  start_time?: string | null;
  timezone?: string | null;
  session_index?: number;
  sport_type?: string;
  workout_type?: string | null;
  title?: string | null;
  is_unplanned?: boolean;
  source_type?: string;
  source_import_batch_id?: number | null;
  external_activity_id?: string | null;
  activity_fingerprint?: string | null;
  field_sources_json?: Record<string, unknown> | null;
  subjective_status?: string;
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
  session_index: number;
  date_text?: string | null;
  weekday?: string | null;
  month_text?: string | null;
  phase_name?: string | null;
  planned_content: string;
  focus_note?: string | null;
  target_pace_text?: string | null;
  planned_distance_km?: number | string | null;
  main_type_raw?: string | null;
  main_type_normalized: WorkoutMainTypeNormalized;
  source_sheet?: string | null;
  source_row?: number | null;
  sort_order: number;
  is_locked: boolean;
  lock_reason?: string | null;
  plan_version: number;
  workout_log?: WorkoutLog | null;
  created_at: string;
  updated_at: string;
}

type PlannedWorkoutWritableFields = Omit<
  PlannedWorkout,
  "id" | "workout_log" | "created_at" | "updated_at"
>;

type PlannedWorkoutServerDefaultFields = "session_index" | "is_locked" | "plan_version";

export type PlannedWorkoutCreatePayload = Omit<
  PlannedWorkoutWritableFields,
  PlannedWorkoutServerDefaultFields
> & Partial<Pick<PlannedWorkoutWritableFields, PlannedWorkoutServerDefaultFields>>;

export type PlannedWorkoutUpdatePayload = Partial<PlannedWorkoutCreatePayload>;

export type PlanImportAnchorStrategy = "after_last_completed" | "explicit_date";
export type PlanImportMergeStrategy =
  | "replace_uncompleted_from_date"
  | "replace_uncompleted_in_range"
  | "append_after_last_planned"
  | "fill_empty_only";
export type PlanImportStatus =
  | "uploaded"
  | "parsed"
  | "validation_failed"
  | "ready"
  | "conflict"
  | "applied"
  | "cancelled"
  | "expired";

export interface PlanImportWorkoutItem {
  planned_date?: string | null;
  day_offset?: number | null;
  session_index?: number;
  workout_type: string;
  title?: string | null;
  planned_distance_km?: number | string | null;
  planned_duration_minutes?: number | null;
  target_pace?: string | null;
  target_rpe?: number | null;
  content: string;
  notes?: string | null;
  is_rest_day?: boolean;
  segments?: unknown[] | null;
}

export interface PlanImportStructuredPayload {
  target_cycle_id?: number | null;
  target_block_id?: number | null;
  source?: string;
  client_request_id?: string | null;
  anchor_strategy: PlanImportAnchorStrategy;
  effective_date?: string | null;
  merge_strategy: PlanImportMergeStrategy;
  timezone?: string;
  workouts: PlanImportWorkoutItem[];
}

export interface PlanImportDiffSummary {
  preserved_count: number;
  created_count: number;
  updated_count: number;
  removed_count: number;
  protected_count: number;
  conflict_count: number;
  warning_count: number;
}

export interface PlanImportIssue {
  item_index?: number | null;
  row_number?: number | null;
  field?: string | null;
  code: string;
  message: string;
}

export interface PlanImportItemRead {
  id: number;
  operation?: string | null;
  planned_date?: string | null;
  session_index?: number | null;
  normalized_item?: PlanImportWorkoutItem | null;
  conflicts?: PlanImportIssue[] | null;
  warnings?: PlanImportIssue[] | null;
  is_selected: boolean;
  is_applied: boolean;
}

export interface PlanImportDraftRead {
  import_id: number;
  status: PlanImportStatus | string;
  effective_date?: string | null;
  merge_strategy?: PlanImportMergeStrategy | string | null;
  anchor_strategy?: PlanImportAnchorStrategy | string | null;
  source_type?: string | null;
  source_name?: string | null;
  normalized_items?: PlanImportWorkoutItem[] | null;
  diff_summary?: PlanImportDiffSummary | null;
  conflicts?: PlanImportIssue[] | null;
  warnings?: PlanImportIssue[] | null;
  items: PlanImportItemRead[];
}

export type WorkoutImportMergeStrategy =
  | "create_missing_only"
  | "fill_empty_fields"
  | "update_objective_fields"
  | "manual_review";

export type WorkoutImportAction =
  | "create_log"
  | "fill_empty_fields"
  | "update_objective_fields"
  | "keep_existing"
  | "link_to_plan"
  | "create_unplanned_log"
  | "skip"
  | "manual_review";

export interface NormalizedWorkoutActivity {
  activity_date: string;
  start_time?: string | null;
  timezone?: string | null;
  session_index?: number;
  sport_type?: string;
  workout_type?: string | null;
  title?: string | null;
  planned_workout_id?: number | null;
  distance_km?: number | string | null;
  duration_seconds?: number | null;
  moving_time_seconds?: number | null;
  elapsed_time_seconds?: number | null;
  average_pace_seconds_per_km?: number | null;
  average_heart_rate_bpm?: number | null;
  max_heart_rate_bpm?: number | null;
  average_cadence_spm?: number | null;
  max_cadence_spm?: number | null;
  elevation_gain_m?: number | null;
  calories_kcal?: number | null;
  rpe?: number | null;
  pain_level?: number | null;
  completion_status?: "completed";
  content?: string | null;
  notes?: string | null;
  external_activity_id?: string | null;
  source?: string | null;
}

export interface WorkoutImportStructuredPayload {
  source?: string;
  timezone?: string;
  merge_strategy: WorkoutImportMergeStrategy;
  client_request_id?: string | null;
  activities: NormalizedWorkoutActivity[];
}

export interface WorkoutImportIssue {
  code: string;
  message: string;
  row_number?: number | null;
  field?: string | null;
}

export interface WorkoutImportPreviewSummary {
  total_count: number;
  matched_plan_count: number;
  matched_log_count: number;
  unplanned_count: number;
  ready_count: number;
  conflict_count: number;
  invalid_count: number;
  skipped_count: number;
}

export interface WorkoutImportItemRead {
  id: number;
  row_number?: number | null;
  activity_date?: string | null;
  start_time?: string | null;
  session_index?: number | null;
  normalized_data_json?: NormalizedWorkoutActivity | null;
  matched_plan_id?: number | null;
  matched_log_id?: number | null;
  match_status: string;
  match_confidence?: string | null;
  suggested_action: WorkoutImportAction | string;
  user_action?: WorkoutImportAction | string | null;
  validation_errors_json?: WorkoutImportIssue[] | null;
  warnings_json?: WorkoutImportIssue[] | null;
  field_diff_json?: Array<Record<string, unknown>> | null;
  activity_fingerprint?: string | null;
}

export interface WorkoutImportBatchRead extends WorkoutImportPreviewSummary {
  id: number;
  status: string;
  source_type: string;
  source_filename?: string | null;
  merge_strategy: WorkoutImportMergeStrategy | string;
  timezone: string;
  client_request_id?: string | null;
  warnings_json?: WorkoutImportIssue[] | null;
  preview_summary_json?: WorkoutImportPreviewSummary | null;
  expires_at?: string | null;
  applied_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;
  items: WorkoutImportItemRead[];
}

export interface WorkoutImportCreateResponse extends WorkoutImportPreviewSummary {
  batch_id: number;
  status: string;
  warnings: WorkoutImportIssue[];
  items: WorkoutImportItemRead[];
  preview_summary: WorkoutImportPreviewSummary;
}

export interface WorkoutImportApplyResponse {
  batch_id: number;
  status: string;
  created_count: number;
  updated_count: number;
  linked_plan_count: number;
  unplanned_count: number;
  skipped_count: number;
  subjective_missing_count: number;
}

export interface GarminConnectionStatus {
  connected: boolean;
  connection_id?: number | null;
  status: string;
  provider: string;
  region?: string | null;
  masked_account_identifier?: string | null;
  auto_import_enabled: boolean;
  auto_sync_enabled?: boolean;
  auto_sync_last_run_at?: string | null;
  last_authenticated_at?: string | null;
  last_successful_sync_at?: string | null;
  last_error_code?: string | null;
  last_error_at?: string | null;
}

export interface GarminConnectPayload {
  username: string;
  password: string;
  region?: string | null;
}

export interface GarminConnectResponse {
  status: string;
  connection?: GarminConnectionStatus | null;
  mfa_token?: string | null;
  safe_message?: string | null;
}

export interface GarminSyncPayload {
  sync_mode: "incremental" | "initial_backfill" | "recent_7d" | "recent_30d" | "custom_range";
  start?: string | null;
  end?: string | null;
}

export interface ProviderCapabilities {
  connect: boolean;
  disconnect: boolean;
  mfa: boolean;
  manual_sync: boolean;
  incremental_sync: boolean;
  initial_backfill: boolean;
  custom_range_sync: boolean;
  activity_reprocess: boolean;
  activity_ignore: boolean;
  activity_restore: boolean;
  auto_import_setting: boolean;
  webhooks: boolean;
}

export interface ProviderDescriptor {
  key: string;
  display_name: string;
  status: string;
  auth_flows: string[];
  capabilities: ProviderCapabilities;
  supported_sync_modes: string[];
  notes?: string | null;
}

export interface DataSyncConnectionRead extends GarminConnectionStatus {
  descriptor?: ProviderDescriptor | null;
}

export interface ProviderListResponse {
  providers: ProviderDescriptor[];
}

export type RunnerStateSnapshotSyncStatus =
  | "PROCESSING"
  | "CREATED"
  | "DUPLICATE_PAYLOAD"
  | "SKIPPED_NO_MATERIAL_CHANGE"
  | "SKIPPED_NOT_COMMITTED"
  | "FAILED_NON_BLOCKING";

export interface RunnerStateSnapshotSyncResult {
  status: RunnerStateSnapshotSyncStatus;
  snapshot_id: number | null;
  error_code: string | null;
}

export interface ExternalSyncJobRead {
  id: number;
  sync_run_id?: string;
  provider: string;
  sync_mode: string;
  requested_start?: string | null;
  requested_end?: string | null;
  status: string;
  fetched_count: number;
  created_count: number;
  updated_count: number;
  duplicate_count: number;
  matched_count: number;
  unplanned_count: number;
  needs_review_count: number;
  ignored_count: number;
  failed_count: number;
  is_committed?: boolean;
  committed_at?: string | null;
  created_log_count?: number;
  updated_log_count?: number;
  unchanged_activity_count?: number;
  runner_state_affecting_change_count?: number;
  started_at?: string | null;
  finished_at?: string | null;
  error_code?: string | null;
  safe_error_message?: string | null;
  created_at: string;
  updated_at: string;
  runner_state_snapshot?: RunnerStateSnapshotSyncResult | null;
}

export interface ExternalActivityRead {
  id: number;
  provider: string;
  external_activity_id: string;
  activity_name?: string | null;
  activity_type: string;
  activity_date: string;
  start_time_local: string;
  processing_status: string;
  resolution_status: string;
  apply_status: string;
  composite_session_key?: string | null;
  match_confidence?: string | null;
  planned_workout_id?: number | null;
  workout_log_id?: number | null;
  distance_m?: number | string | null;
  duration_seconds?: number | null;
  average_pace_seconds_per_km?: number | null;
  average_heart_rate_bpm?: number | null;
  max_heart_rate_bpm?: number | null;
  data_quality: string;
  quality_warnings_json?: string[] | null;
}

export interface GarminActivityReconcilePayload {
  start_date?: string | null;
  end_date?: string | null;
  dry_run?: boolean;
  activity_ids?: number[] | null;
}

export interface GarminActivityReconcileSummary {
  dry_run: boolean;
  activity_count: number;
  estimated_session_count: number;
  estimated_matched_plan_count: number;
  estimated_merged_existing_log_count: number;
  estimated_unplanned_log_count: number;
  needs_review_count: number;
  conflict_count: number;
  applied_count: number;
}

export interface WorkoutLogGarminActivityContext {
  id: number;
  activity_name?: string | null;
  activity_date: string;
  start_time_local: string;
  distance_m?: number | string | null;
  duration_seconds?: number | null;
  average_pace_seconds_per_km?: number | null;
  average_heart_rate_bpm?: number | null;
  resolution_status: string;
  apply_status: string;
}

export interface WorkoutCompletionContext {
  existing_workout_log?: WorkoutLog | null;
  linked_garmin_activities: WorkoutLogGarminActivityContext[];
  candidate_garmin_activities: WorkoutLogGarminActivityContext[];
  prefilled_objective_fields: Record<string, unknown>;
  subjective_fields_missing: string[];
  field_conflicts: Array<Record<string, unknown>>;
  mode: "manual_full" | "device_prefilled" | "garmin_prefilled" | "merge_conflict" | "already_completed" | "pending_sync" | string;
}

export interface TaskItem {
  task_key: string;
  task_type: string;
  title: string;
  description?: string | null;
  priority: number;
  count: number;
  action_path: string;
  source_type?: string | null;
  source_id?: number | null;
  created_at?: string | null;
}

export interface TaskListResponse {
  items: TaskItem[];
  total: number;
}

export interface DataSyncProviderSummary {
  provider: string;
  connected: boolean;
  status: string;
  masked_account_identifier?: string | null;
  auto_import_enabled: boolean;
  auto_sync_enabled: boolean;
  auto_sync_last_run_at?: string | null;
  last_successful_sync_at?: string | null;
  last_error_code?: string | null;
}

export interface DataSyncSummary {
  providers: DataSyncProviderSummary[];
  connected_count: number;
  needs_review_count: number;
  failed_job_count: number;
}

export interface TrainingPlanOverview {
  has_active_cycle: boolean;
  active_cycle?: TrainingCycle | null;
  current_block?: Record<string, unknown> | null;
  week_start: string;
  week_end: string;
  week_workouts: PlannedWorkout[];
  primary_actions: Array<{ label: string; path: string }>;
  advanced_links: Array<{ label: string; path: string }>;
}

export interface TodayDashboard {
  today: string;
  has_active_cycle: boolean;
  workouts: PlannedWorkout[];
  tasks: TaskItem[];
  data_sync: DataSyncSummary;
  recovery_checkin_completed: boolean;
}

export interface RecoveryQuickPayload {
  leg_feeling: "good" | "normal" | "bad";
  fatigue: "low" | "normal" | "high";
  pain: "none" | "mild" | "obvious";
}

export interface RecoveryQuickRead extends Partial<RecoveryQuickPayload> {
  checkin_date: string;
  raw?: Record<string, unknown> | null;
}

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
  source_type?: string | null;
  subjective_status?: string | null;
  has_garmin_activity?: boolean;
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

export type TrainingStatus = "insufficient_data" | "normal" | "watch" | "reduce_load";
export type ReadinessDataQuality = "low" | "medium" | "high";
export type PainTrend = "improving" | "stable" | "worsening" | "unknown";

export interface RecoveryCheckinPayload {
  sleep_duration_minutes?: number | null;
  sleep_quality?: number | null;
  subjective_fatigue?: number | null;
  muscle_soreness?: number | null;
  stress_level?: number | null;
  mood_level?: number | null;
  leg_feeling?: number | null;
  resting_heart_rate_bpm?: number | null;
  hrv_value?: number | string | null;
  hrv_metric?: string | null;
  hrv_source?: string | null;
  pain_level?: number | null;
  pain_location?: string | null;
  pain_trend?: PainTrend;
  pain_affects_gait?: boolean | null;
  illness_symptoms?: string | null;
  notes?: string | null;
}

export interface RecoveryCheckin extends RecoveryCheckinPayload {
  id: number;
  checkin_date: string;
  source: "manual";
  created_at: string;
  updated_at: string;
}

export interface DailyTrainingLoad {
  load_date: string;
  distance_km: number;
  duration_minutes: number;
  srpe_load_au?: number | null;
  easy_distance_km: number;
  moderate_distance_km: number;
  high_intensity_distance_km: number;
  key_workout_count: number;
  training_session_count: number;
}

export interface TrainingLoadSummaryRead {
  assessment_date: string;
  rolling_7d_distance_km: number;
  rolling_7d_duration_minutes: number;
  rolling_7d_srpe_load_au?: number | null;
  rolling_7d_high_intensity_distance_km: number;
  rolling_7d_key_workout_count: number;
  rolling_7d_training_session_count: number;
  baseline_28d_total_distance_km: number;
  baseline_28d_weekly_distance_km: number;
  baseline_28d_total_srpe_load_au?: number | null;
  baseline_28d_weekly_srpe_load_au?: number | null;
  baseline_28d_avg_rpe?: number | null;
  srpe_coverage_ratio: number;
  recovery_checkin_coverage_ratio: number;
  recent_to_baseline_load_ratio?: number | null;
  load_change_percentage?: number | null;
  distance_change_percentage?: number | null;
  history_days: number;
  missing_data: string[];
}

export interface TrainingReadinessAssessment {
  id: number;
  assessment_date: string;
  status: TrainingStatus;
  data_quality: ReadinessDataQuality;
  metrics_json: TrainingLoadSummaryRead;
  external_load_signals_json?: Array<Record<string, unknown>> | null;
  internal_load_signals_json?: Array<Record<string, unknown>> | null;
  recovery_signals_json?: Array<Record<string, unknown>> | null;
  performance_signals_json?: Array<Record<string, unknown>> | null;
  pain_signals_json?: Array<Record<string, unknown>> | null;
  reasons_json: string[];
  recommendations_json: Array<{ action: string; message: string; reason: string; requires_confirmation: boolean }>;
  missing_data_json?: string[] | null;
  algorithm_version: string;
  threshold_version: string;
  generated_at: string;
  created_at: string;
  updated_at: string;
}

export interface TrainingReadinessToday {
  assessment: TrainingReadinessAssessment;
  recovery_checkin_completed: boolean;
}

export type RuleAction =
  | "no_action"
  | "show_info"
  | "keep_plan"
  | "monitor"
  | "adjust_recommended"
  | "downgrade_recommended"
  | "rest_recommended"
  | "require_user_review"
  | "block_auto_apply"
  | string;

export interface RuleMatchedItem {
  rule_code: string;
  rule_version: string;
  severity: "info" | "notice" | "caution" | "high" | "blocking" | string;
  priority: number;
  action: RuleAction;
  recommendation?: string | null;
  explanation: string;
  output: Record<string, unknown>;
}

export interface RuleEvaluationResult {
  evaluation_id?: number | null;
  context_type: string;
  final_action: RuleAction;
  dominant_rule_code?: string | null;
  matched_rules: RuleMatchedItem[];
  conflict_resolution: Record<string, unknown>;
  recommendations: string[];
  engine_version: string;
  ruleset_version: string;
}

export interface RuleLoopSummary {
  blocking: number;
  high: number;
  caution: number;
  notice: number;
  info: number;
}

export interface RuleLoopEvaluation {
  validation_status: string;
  title: string;
  message: string;
  data_limited: boolean;
  summary: RuleLoopSummary;
  evaluation: RuleEvaluationResult;
  facts_hash?: string | null;
  generated_adjustment_draft_id?: number | null;
  evaluated_at?: string | null;
}

export interface TrainingAdjustmentDraft {
  id: number;
  source_type: string;
  source_evaluation_id?: number | null;
  cycle_id?: number | null;
  week_start?: string | null;
  status: string;
  adjustment_json: Record<string, unknown>;
  explanation_json: Record<string, unknown>;
  original_plan_snapshot_json: Record<string, unknown>;
  applied_result_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}
export type AdjustmentAction = "keep" | "reduce" | "replace" | "rest";
export type AdjustmentDraftStatus = "draft" | "partially_applied" | "applied" | "rejected" | "invalid";

export interface WeeklyReviewMetrics {
  week_start_date: string;
  week_end_date: string;
  is_week_complete: boolean;
  planned_distance_km: number;
  actual_distance_km: number;
  completion_rate: number;
  planned_workout_days: number;
  completed_workout_days: number;
  completed_high_count: number;
  completed_normal_count: number;
  completed_adjusted_count: number;
  missed_count: number;
  rest_count: number;
  skipped_count: number;
  avg_rpe?: number | null;
  key_workout_avg_rpe?: number | null;
  max_pain_level?: number | null;
  planned_type_distance: Record<string, number>;
  actual_type_distance: Record<string, number>;
  key_workouts: Array<Record<string, unknown>>;
  long_run?: Record<string, unknown> | null;
  recent_7d_distance_km: number;
  recent_28d_weekly_avg_km: number;
  rolling_7d_srpe_load_au?: number | null;
  baseline_28d_weekly_srpe_load_au?: number | null;
  recent_to_baseline_load_ratio?: number | null;
  recovery_checkin_coverage_ratio?: number | null;
  readiness_data_quality?: ReadinessDataQuality | null;
  readiness_status?: TrainingStatus | null;
  load_change_percentage?: number | null;
  consecutive_high_intensity_days: string[][];
  logged_workout_ratio: number;
  valid_log_count: number;
  missing_fields: string[];
  daily_workouts: Array<{
    planned_workout_id: number;
    date?: string | null;
    planned_content: string;
    planned_distance_km: number;
    actual_distance_km: number;
    main_type: WorkoutMainTypeNormalized;
    status: WorkoutStatusNormalized;
    rpe?: number | null;
  }>;
}

export interface TrainingStatusResult {
  status: TrainingStatus;
  reasons: string[];
  signals: Array<{ code: string; level: string; message: string }>;
  missing_data: string[];
}

export interface WeeklyReviewSummary {
  metrics: WeeklyReviewMetrics;
  training_status: TrainingStatusResult;
}

export interface AdjustmentItem {
  id: number;
  draft_id: number;
  planned_workout_id: number;
  workout_date?: string | null;
  action: AdjustmentAction;
  original_content: string;
  suggested_content: string;
  original_distance_km?: number | null;
  suggested_distance_km?: number | null;
  original_main_type?: string | null;
  suggested_main_type?: string | null;
  original_target_pace_text?: string | null;
  suggested_target_pace_text?: string | null;
  reason: string;
  is_selected: boolean;
  is_applied: boolean;
}

export interface AdjustmentDraft {
  id: number;
  review_report_id: number;
  cycle_id: number;
  source_block_id: number;
  target_block_id: number;
  status: AdjustmentDraftStatus;
  summary?: string | null;
  original_week_distance_km?: number | null;
  suggested_week_distance_km?: number | null;
  items: AdjustmentItem[];
}

export interface WeeklyReviewReport {
  id: number;
  cycle_id: number;
  source_block_id: number;
  target_block_id?: number | null;
  week_start_date: string;
  week_end_date: string;
  version: number;
  status: "pending" | "generating" | "success" | "failed";
  training_status: TrainingStatus;
  metrics_json: WeeklyReviewMetrics;
  rule_reasons_json?: string[] | null;
  missing_data_json?: string[] | null;
  summary?: string | null;
  positive_points_json?: string[] | null;
  attention_points_json?: string[] | null;
  next_week_strategy?: string | null;
  risk_notes_json?: string[] | null;
  model_name?: string | null;
  created_at: string;
}

export interface WeeklyReviewDetail {
  report: WeeklyReviewReport;
  adjustment_draft?: AdjustmentDraft | null;
}

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

export type AuthEntryMode = "standalone" | "modal";

export interface SystemSettings {
  id?: number | null;
  auth_entry_mode: AuthEntryMode;
  allow_public_registration: boolean;
  updated_at?: string | null;
}

export type SystemSettingsPayload = Pick<SystemSettings, "auth_entry_mode" | "allow_public_registration">;

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
