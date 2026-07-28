import type {
  CoachKnowledgeReference,
  CoachQueryResponse,
} from "@/types/coachAgent";
import { createCoachResponse } from "@/test/coachAgentFixture";

export type CoachRagDemoScenario = "general" | "explain" | "today" | "degraded";

export const coachRagDemoQuestions: Record<CoachRagDemoScenario, string> = {
  general: "阈值训练通常应该怎样安排？",
  explain: "请解释当前虚构 Runner State，以及数据不足带来的限制。",
  today: "根据虚构计划和状态，今天应该怎样训练？",
  degraded: "模型或训练知识暂不可用时，今天应该怎样训练？",
};

const THRESHOLD_REFERENCE: CoachKnowledgeReference = {
  document_id: "public-threshold-principles",
  title: "阈值训练的强度控制原则",
  section: "训练目的与执行边界",
  source_id: "public-training-knowledge",
  source_title: "GaitLogic 公开训练知识库",
  knowledge_version: "corpus-v1",
  evidence_level: "EXPERT_CONSENSUS",
  excerpt: "阈值训练应围绕可持续的受控强度展开，并根据训练阶段和恢复状态安排。",
  limitations: ["具体配速仍需结合个人训练数据和当前状态。"],
};

const RECOVERY_REFERENCE: CoachKnowledgeReference = {
  document_id: "public-recovery-principles",
  title: "恢复不足时的训练安排",
  section: "负荷与恢复",
  source_id: "public-training-knowledge",
  source_title: "GaitLogic 公开训练知识库",
  knowledge_version: "corpus-v1",
  evidence_level: "SECONDARY",
  excerpt: "当恢复信息不完整或疲劳信号增加时，应保留调整空间并避免把单一指标解释为确定结论。",
  limitations: ["不用于伤病诊断或医疗决策。"],
};

export const coachRagDemoFixtures: Record<CoachRagDemoScenario, CoachQueryResponse> = {
  general: createCoachResponse({
    request_id: "31111111-1111-4111-8111-111111111111",
    intent: "GENERAL_TRAINING_QUESTION",
    answer: "阈值训练通常安排在恢复较好的日期，并与其他高强度训练保持合理间隔。",
    summary: "以受控强度和充分恢复为前提安排阈值训练。",
    risk_level: "UNKNOWN",
    today_recommendation: null,
    knowledge_references: [THRESHOLD_REFERENCE, RECOVERY_REFERENCE],
    tool_calls: [
      {
        tool_name: "retrieve_training_knowledge",
        status: "SUCCEEDED",
        safe_error_code: null,
      },
    ],
    limitations: [
      {
        code: "NO_PERSONAL_CONTEXT",
        message: "这是一般训练知识说明，未使用个人训练数据。",
      },
    ],
  }),
  explain: createCoachResponse({
    request_id: "32222222-2222-4222-8222-222222222222",
    intent: "EXPLAIN_RUNNER_STATE",
    answer: "当前虚构状态显示中等疲劳，需要结合近期训练规律和数据质量谨慎解释。",
    summary: "中等疲劳，建议关注恢复信息和近期负荷变化。",
    risk_level: "MODERATE",
    today_recommendation: null,
    knowledge_references: [RECOVERY_REFERENCE],
    tool_calls: [
      { tool_name: "get_runner_state", status: "SUCCEEDED", safe_error_code: null },
      {
        tool_name: "retrieve_training_knowledge",
        status: "SUCCEEDED",
        safe_error_code: null,
      },
    ],
    limitations: [
      {
        code: "DATA_LIMITED",
        message: "虚构场景中部分恢复字段缺失，结论不能视为医疗判断。",
      },
    ],
  }),
  today: createCoachResponse({
    request_id: "33333333-3333-4333-8333-333333333333",
    answer: "知识依据支持保留调整空间，但不会改变系统规则给出的谨慎执行结论。",
    summary: "按确定性建议谨慎执行，并根据主观恢复情况人工确认。",
    risk_level: "MODERATE",
    today_recommendation: {
      decision: "PROCEED_WITH_CAUTION",
      planned_workout_status: "PLANNED",
      headline: "建议谨慎执行今天的虚构训练计划。",
      key_evidence: ["FICTIONAL_RECOVERY_SIGNAL", "FICTIONAL_PLANNED_SESSION"],
      data_quality: "PARTIAL",
    },
    knowledge_references: [THRESHOLD_REFERENCE, RECOVERY_REFERENCE],
    tool_calls: [
      { tool_name: "get_runner_state", status: "SUCCEEDED", safe_error_code: null },
      { tool_name: "get_today_workout", status: "SUCCEEDED", safe_error_code: null },
      { tool_name: "get_recent_training", status: "SUCCEEDED", safe_error_code: null },
      {
        tool_name: "retrieve_training_knowledge",
        status: "SUCCEEDED",
        safe_error_code: null,
      },
      {
        tool_name: "evaluate_today_workout",
        status: "SUCCEEDED",
        safe_error_code: null,
      },
    ],
    warnings: [
      {
        code: "FICTIONAL_RECOVERY_REVIEW",
        message: "开始训练前请人工确认主观恢复情况，必要时降低强度。",
      },
    ],
    limitations: [
      {
        code: "DATA_LIMITED",
        message: "睡眠和腿部感受为虚构缺失字段，建议不构成医疗诊断。",
      },
    ],
  }),
  degraded: createCoachResponse({
    request_id: "34444444-4444-4444-8444-444444444444",
    status: "DEGRADED",
    answer: "模型解释暂不可用，当前仅展示系统规则和虚构训练事实。",
    summary: "确定性安全降级结果仍然可用。",
    provider_status: "FAILED",
    knowledge_references: [],
    tool_calls: [
      { tool_name: "get_runner_state", status: "SUCCEEDED", safe_error_code: null },
      {
        tool_name: "retrieve_training_knowledge",
        status: "FAILED",
        safe_error_code: "AGENT_TOOL_EXECUTION_FAILED",
      },
    ],
    limitations: [
      {
        code: "MODEL_EXPLANATION_UNAVAILABLE",
        message: "模型解释暂不可用，当前内容由确定性规则生成。",
      },
      {
        code: "KNOWLEDGE_RETRIEVAL_UNAVAILABLE",
        message: "训练知识暂时不可用，本次未使用知识库引用。",
      },
    ],
  }),
};

export function getCoachRagDemoScenario(
  search: string,
): CoachRagDemoScenario | null {
  const value = new URLSearchParams(search).get("demo");
  return value && value in coachRagDemoFixtures
    ? value as CoachRagDemoScenario
    : null;
}

export function createCoachRagDemoResponse(
  scenario: CoachRagDemoScenario,
): CoachQueryResponse {
  return structuredClone(coachRagDemoFixtures[scenario]);
}
