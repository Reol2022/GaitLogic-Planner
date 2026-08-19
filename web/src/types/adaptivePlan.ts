export type WeeklyClassificationStatus =
  | "ON_TRACK"
  | "UNDER_COMPLETED"
  | "OVER_COMPLETED"
  | "INTENSITY_IMBALANCE"
  | "RECOVERY_CONCERN"
  | "MIXED"
  | "INSUFFICIENT_DATA";

export interface WeeklyFacts {
  period: { week_start: string; week_end: string; timezone: string; training_phase?: string | null };
  planned: {
    planned_running_session_count: number;
    planned_distance_km: number | null;
    planned_key_session_count: number;
    planned_high_intensity_session_count: number;
  };
  completed: {
    completed_running_session_count: number;
    actual_distance_km: number | null;
    completed_key_session_count: number;
    partial_session_count: number;
    missed_session_count: number;
    extra_session_count: number;
  };
  adherence: { session_completion_rate: number | null; distance_completion_rate: number | null };
  deviations: Array<{
    deviation_type: string;
    date: string;
    severity: "INFO" | "WARNING" | "ATTENTION";
    evidence_codes: string[];
  }>;
  runner_state_trend: { current_runner_state: string; fatigue_level: string };
  data_quality: { level: "COMPLETE" | "PARTIAL" | "INSUFFICIENT" | "CONFLICTED" };
  classification: {
    primary_status: WeeklyClassificationStatus;
    rule_codes: string[];
    evidence_codes: string[];
    warnings: string[];
    limitations: string[];
    overall_readiness?: "READY" | "PARTIAL" | "BLOCKED" | "NOT_APPLICABLE" | null;
    domain_readiness?: Array<{ domain: string; readiness: "READY" | "PARTIAL" | "BLOCKED" | "NOT_APPLICABLE"; limitations?: string[] }>;
    hard_blockers?: string[];
    data_limitations?: string[];
    capability_limitations?: string[];
  };
  result_hash: string;
}

export interface WeeklyKnowledgeReference {
  document_id: string;
  title: string;
  section: string;
  source_id: string;
  source_title: string;
  knowledge_version: string;
  evidence_level: string;
  excerpt: string;
  limitations: string[];
}

export interface LangGraphWeeklyReview {
  weekly_facts: WeeklyFacts;
  rule_results: string[];
  overview: string;
  completion_summary: string;
  key_session_summary: string;
  deviation_summary: string;
  fatigue_and_risk: string;
  next_week_focus: string[];
  warnings: string[];
  limitations: string[];
  knowledge_references: WeeklyKnowledgeReference[];
  fallback_used: boolean;
  proposal_record_id?: number | null;
}

export interface AdaptivePlanValue {
  content: string;
  distance_km: number | null;
  main_type: string;
  target_pace_text?: string | null;
}

export interface AdaptivePlanChange {
  date: string;
  plan_id: number;
  base_plan_version: number;
  action: "keep" | "reduce" | "replace" | "rest";
  before: AdaptivePlanValue;
  after: AdaptivePlanValue;
  reason: string;
  rule_evidence: string[];
}

export interface AdaptiveProposal {
  id: number;
  week_start: string | null;
  status: string;
  proposal: {
    reason_codes: string[];
    changes: AdaptivePlanChange[];
    warnings: string[];
    limitations: string[];
  };
  created_at: string;
  updated_at: string;
}

export interface AdaptiveApprovalResult {
  proposal_id: number;
  status: string;
  plan_version_id: number | null;
  applied_plan_ids: number[];
  duplicate: boolean;
}
