import type { CoachQueryResponse } from "@/types/coachAgent";

export function createCoachResponse(
  overrides: Partial<CoachQueryResponse> = {},
): CoachQueryResponse {
  return {
    request_id: "11111111-1111-4111-8111-111111111111",
    trace_id: "22222222-2222-4222-8222-222222222222",
    status: "SUCCEEDED",
    intent: "TODAY_RECOMMENDATION",
    answer: "根据现有规则，可以按虚构的原计划执行。",
    summary: "按原计划执行",
    risk_level: "LOW",
    today_recommendation: {
      decision: "PROCEED",
      planned_workout_status: "PLANNED",
      headline: "可以按原计划执行。",
      key_evidence: ["FICTIONAL_PUBLIC_RULE"],
      data_quality: "AVAILABLE",
    },
    tool_calls: [
      { tool_name: "get_runner_state", status: "SUCCEEDED", safe_error_code: null },
      { tool_name: "evaluate_today_workout", status: "SUCCEEDED", safe_error_code: null },
    ],
    warnings: [],
    limitations: [],
    knowledge_references: [],
    provider_status: "SUCCEEDED",
    generated_at: "2026-07-23T09:00:00+08:00",
    ...overrides,
  };
}
