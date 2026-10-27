export type CoachAgentIntent =
  | "TODAY_RECOMMENDATION"
  | "EXPLAIN_RUNNER_STATE"
  | "GENERAL_TRAINING_QUESTION";

export type CoachQueryStatus =
  | "SUCCEEDED"
  | "DEGRADED"
  | "VALIDATION_FAILED"
  | "REJECTED"
  | "UNAVAILABLE";

export type CoachRiskLevel = "LOW" | "MODERATE" | "HIGH" | "UNKNOWN";

export type CoachTodayDecision =
  | "PROCEED"
  | "PROCEED_WITH_CAUTION"
  | "CONSIDER_ADJUSTMENT"
  | "REST_OR_RECOVERY"
  | "UNKNOWN";

export type CoachPlannedWorkoutStatus =
  | "PLANNED"
  | "REST_DAY"
  | "NO_PLAN"
  | "CYCLE_NOT_ACTIVE"
  | "UNKNOWN";

export type CoachProviderStatus =
  | "SUCCEEDED"
  | "DISABLED"
  | "UNCONFIGURED"
  | "FAILED"
  | "NOT_CALLED";

export type CoachToolStatus =
  | "SUCCEEDED"
  | "FAILED"
  | "NOT_FOUND"
  | "NOT_ALLOWED"
  | "INVALID_ARGUMENTS";

export type CoachKnowledgeEvidenceLevel =
  | "PRIMARY"
  | "SECONDARY"
  | "EXPERT_CONSENSUS"
  | "INTERNAL"
  | "UNKNOWN";

export type CoachKnowledgeStatus =
  | "USED"
  | "EMPTY"
  | "UNAVAILABLE"
  | "DISABLED";

export type CoachConversationRole = "user" | "assistant";

export interface CoachConversationMessage {
  role: CoachConversationRole;
  content: string;
}

export interface CoachQueryRequest {
  message: string;
  intent?: CoachAgentIntent;
  conversation_context?: CoachConversationMessage[];
}

export interface CoachNotice {
  code: string;
  message: string;
}

export interface CoachTodayRecommendation {
  decision: CoachTodayDecision;
  planned_workout_status: CoachPlannedWorkoutStatus;
  headline: string;
  key_evidence: string[];
  data_quality: string;
}

export interface CoachToolCallSummary {
  tool_name: string;
  status: CoachToolStatus;
  safe_error_code?: string | null;
}

export interface CoachKnowledgeReference {
  document_id: string;
  title: string;
  section: string;
  source_id: string;
  source_title: string;
  knowledge_version: string;
  evidence_level: CoachKnowledgeEvidenceLevel;
  excerpt: string;
  limitations: string[];
}

export interface CoachQueryResponse {
  request_id: string;
  trace_id: string;
  status: CoachQueryStatus;
  intent: CoachAgentIntent;
  answer?: string | null;
  summary?: string | null;
  risk_level: CoachRiskLevel;
  today_recommendation?: CoachTodayRecommendation | null;
  tool_calls: CoachToolCallSummary[];
  warnings: CoachNotice[];
  limitations: CoachNotice[];
  /**
   * Optional for compatibility with responses produced before v0.12.0.
   * The server only returns materialized public references, never internal
   * reference IDs, chunk IDs, paths, scores, or vectors.
   */
  knowledge_references?: CoachKnowledgeReference[];
  training_fact_context?: CoachTrainingFactContext | null;
  provider_status: CoachProviderStatus;
  generated_at: string;
}

export interface CoachTrainingFactContext {
  range_start: string;
  range_end: string;
  range_label: string;
  as_of: string;
  sources: string[];
  gaps: string[];
  issues: CoachNotice[];
}

export type CoachConversationStatus = "active" | "archived";
export type CoachStoredMessageStatus = "pending" | "completed" | "failed";
export type CoachTurnStage =
  | "QUEUED"
  | "CONTEXT_LOADING"
  | "FACTS_LOADING"
  | "FACTS_READY"
  | "GENERATING"
  | "VALIDATING"
  | "COMPLETED"
  | "FAILED";

export interface CoachProgressItem {
  code: string;
  message: string;
  count?: number | null;
}

export interface CoachTurnProgress {
  stage: CoachTurnStage;
  sequence: number;
  updated_at?: string | null;
  summary: CoachProgressItem[];
  terminal: boolean;
}

export interface CoachConversation {
  id: string;
  title: string;
  status: CoachConversationStatus;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
  message_count: number;
}

export interface CoachConversationPage {
  items: CoachConversation[];
  page: number;
  page_size: number;
  total: number;
}

export interface CoachStoredMessage {
  id: string;
  role: CoachConversationRole;
  content?: string | null;
  status: CoachStoredMessageStatus;
  sequence_no: number;
  response_kind?: string | null;
  evidence_refs: CoachKnowledgeReference[];
  proposal_ref?: string | null;
  trace_id?: string | null;
  created_at: string;
  completed_at?: string | null;
  warnings: CoachNotice[];
  limitations: CoachNotice[];
  tool_calls: CoachToolCallSummary[];
  today_recommendation?: CoachTodayRecommendation | null;
  training_fact_context?: CoachTrainingFactContext | null;
  progress?: CoachTurnProgress | null;
}

export interface CoachMessagePage {
  items: CoachStoredMessage[];
  page: number;
  page_size: number;
  total: number;
}

export interface CoachConversationMessageResult {
  conversation_id: string;
  message_id: string;
  status: CoachStoredMessageStatus;
  content?: string | null;
  response?: CoachQueryResponse | null;
}

export interface CoachConversationTurnStatus {
  conversation_id: string;
  message_id: string;
  message_status: CoachStoredMessageStatus;
  client_turn_id: string;
  progress: CoachTurnProgress;
}
