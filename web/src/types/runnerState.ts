export type VolumeTrendState = "UNKNOWN" | "DECREASING" | "STABLE" | "INCREASING" | "SPIKING";
export type TrainingConsistencyState = "UNKNOWN" | "LOW" | "MODERATE" | "HIGH";
export type FatigueState = "UNKNOWN" | "NORMAL" | "ELEVATED" | "HIGH";
export type TrainingPhaseState = "UNKNOWN" | "BASE" | "BUILD" | "SPECIFIC" | "PEAK" | "TAPER" | "RACE" | "RECOVERY";
export type InferenceBasis = "PLAN_COMPLETION" | "ACTIVITY_REGULARITY";
export type RiskSeverity = "INFO" | "WARNING" | "ATTENTION";
export type SuggestedActionType =
  | "REVIEW"
  | "REVIEW_RECOVERY"
  | "REDUCE_LOAD"
  | "ADD_RECOVERY"
  | "COLLECT_MORE_DATA"
  | "MANUAL_CONFIRMATION";

export interface RunnerStateEvidence {
  metric: string;
  value?: number | string | null;
  threshold?: number | string | null;
  unit?: string | null;
  window: string;
  source: string;
  used: boolean;
}

export interface RunnerStateIdentity {
  runner_id: number;
  generated_at: string;
  timezone: string;
  calculation_window_end: string;
  calculation_window_start_7d: string;
  calculation_window_start_28d: string;
}

export interface RunnerRecentTrainingMetrics {
  distance_7d_km?: number | null;
  distance_28d_km?: number | null;
  duration_7d_minutes?: number | null;
  duration_28d_minutes?: number | null;
  sessions_7d: number;
  sessions_28d: number;
  completed_sessions_7d: number;
  completed_sessions_28d: number;
  planned_sessions_7d: number;
  planned_sessions_28d: number;
  completion_rate_7d?: number | null;
  completion_rate_28d?: number | null;
  average_rpe_7d?: number | null;
  average_rpe_28d?: number | null;
}

export interface RunnerIntensityMetrics {
  easy_distance_7d_km?: number | null;
  moderate_distance_7d_km?: number | null;
  hard_distance_7d_km?: number | null;
  easy_distance_28d_km?: number | null;
  moderate_distance_28d_km?: number | null;
  hard_distance_28d_km?: number | null;
  hard_distance_ratio_7d?: number | null;
  hard_distance_ratio_28d?: number | null;
  quality_sessions_7d: number;
  quality_sessions_28d: number;
  long_run_distance_7d_km?: number | null;
  long_run_distance_28d_km?: number | null;
  days_since_last_quality_session?: number | null;
}

export interface RunnerStateDerivedMetrics {
  distance_previous_21d_km?: number | null;
  sessions_previous_21d: number;
  valid_workout_count_previous_21d?: number;
  average_rpe_previous_21d?: number | null;
  rpe_coverage_previous_21d: number;
  planned_sessions_previous_21d: number;
  completed_planned_sessions_previous_21d: number;
  completion_rate_previous_21d?: number | null;
  active_weeks_previous_21d: number;
  active_weeks_28d: number;
  weekly_session_mean_28d: number;
  weekly_session_cv_28d?: number | null;
  high_intensity_sessions_7d: number;
  high_intensity_sessions_28d: number;
  maximum_consecutive_high_intensity_days_7d: number;
}

export interface RunnerStateInferenceResult<TState extends string> {
  state: TState;
  reason_codes: string[];
  evidence: RunnerStateEvidence[];
  ruleset_version: string;
}

export interface VolumeTrendInference extends RunnerStateInferenceResult<VolumeTrendState> {
  previous_21d_weekly_average_km?: number | null;
  volume_ratio?: number | null;
}

export interface TrainingConsistencyInference extends RunnerStateInferenceResult<TrainingConsistencyState> {
  basis?: InferenceBasis | null;
  evidence_coverage: number;
}

export interface FatigueInference extends RunnerStateInferenceResult<FatigueState> {
  score: number;
  triggered_signals: string[];
  skipped_signals: string[];
  available_signal_count: number;
  total_signal_count: number;
  evidence_coverage: number;
}

export interface RunnerStateRiskFlag {
  code: string;
  severity: RiskSeverity;
  message: string;
  suggested_action_type: SuggestedActionType;
  triggered_rule: string;
  evidence: RunnerStateEvidence[];
}

export interface RunnerStateDataQuality {
  data_quality_level: "NONE" | "LOW" | "MEDIUM" | "HIGH";
  confidence: number;
  available_fields: string[];
  missing_fields: string[];
  valid_workout_count_7d: number;
  valid_workout_count_28d: number;
  rpe_coverage_7d: number;
  rpe_coverage_28d: number;
  heart_rate_coverage_7d: number;
  heart_rate_coverage_28d: number;
  limitations: string[];
}

export interface RunnerStateSnapshot {
  identity: RunnerStateIdentity;
  goal_context: {
    race_distance?: string | null;
    race_date?: string | null;
    target_time_seconds?: number | null;
    weeks_remaining?: number | null;
  };
  recent_training: RunnerRecentTrainingMetrics;
  intensity: RunnerIntensityMetrics;
  inferred_state: {
    fitness_state: "UNKNOWN";
    fatigue_state: FatigueState;
    load_trend: "UNKNOWN";
    training_consistency: TrainingConsistencyState;
    training_phase: TrainingPhaseState;
    weaknesses: string[];
    risk_flags: string[];
  };
  data_quality: RunnerStateDataQuality;
  derived_metrics?: RunnerStateDerivedMetrics | null;
  volume_trend?: VolumeTrendInference | null;
  training_consistency?: TrainingConsistencyInference | null;
  fatigue?: FatigueInference | null;
  risk_flags?: RunnerStateRiskFlag[];
  inference_metadata?: {
    ruleset_version: string;
    calculated_at: string;
    reason_codes: string[];
    limitations: string[];
  } | null;
}

export interface RunnerStateCurrentResponse {
  snapshot: RunnerStateSnapshot;
}
