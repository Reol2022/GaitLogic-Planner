import request from "./request";

export interface EvidenceSource {
  id: number;
  code: string;
  title: string;
  source_type: string;
  evidence_level: string;
  review_status: string;
  publication_year?: number | null;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface RuleCoverage {
  published_rules: number;
  rules_with_positive_case: number;
  rules_with_negative_case: number;
  rules_with_boundary_case: number;
  rules_with_conflict_case: number;
  uncovered_rules: string[];
  by_scope: Record<string, { total: number; covered: number }>;
  by_severity: Record<string, { total: number; covered: number }>;
}

export interface RuleMetrics {
  rule_hits: Record<string, number>;
  dominant_counts: Record<string, number>;
  action_distribution: Record<string, number>;
  severity_distribution: Record<string, number>;
  context_distribution: Record<string, number>;
  status_counts: Record<string, number>;
}

export interface RuleTestRun {
  id: number;
  ruleset_version: string;
  run_type: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  result_summary_json: Record<string, unknown>;
  started_at: string;
  finished_at?: string | null;
}

export function listTrainingEvidence() {
  return request.get<EvidenceSource[]>("/admin/training-evidence");
}

export function getRuleCoverage() {
  return request.get<RuleCoverage>("/admin/training-rules/coverage");
}

export function getRuleMetrics() {
  return request.get<RuleMetrics>("/admin/training-rules/metrics");
}

export function listRuleTestRuns() {
  return request.get<RuleTestRun[]>("/admin/training-rule-tests/runs");
}

export function runRuleRegression() {
  return request.post<RuleTestRun>("/admin/training-rule-tests/run", { run_type: "regression" });
}
