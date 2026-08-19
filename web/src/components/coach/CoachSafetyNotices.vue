<template>
  <section v-if="warnings.length || limitations.length" class="notice-stack" aria-label="建议提示和限制">
    <div v-if="warnings.length" class="warning-panel" role="alert">
      <h2>{{ riskLevel === "HIGH" ? "需要重点关注" : "训练提示" }}</h2>
      <ul>
        <li v-for="notice in warnings" :key="`${notice.code}-${notice.message}`">
          <strong>{{ warningTitle(notice.code) }}</strong>
          <span>{{ noticeMessage(notice) }}</span>
        </li>
      </ul>
    </div>
    <div v-if="limitations.length" class="limitation-panel" role="status">
      <h2>结论限制</h2>
      <ul>
        <li v-for="notice in limitations" :key="`${notice.code}-${notice.message}`">
          <strong>{{ limitationTitle(notice) }}</strong>
          <span>{{ noticeMessage(notice) }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { CoachNotice, CoachRiskLevel } from "@/types/coachAgent";
import { limitationMessage } from "@/utils/limitationDisplay";

withDefaults(defineProps<{
  warnings?: CoachNotice[];
  limitations?: CoachNotice[];
  riskLevel?: CoachRiskLevel;
}>(), {
  warnings: () => [],
  limitations: () => [],
  riskLevel: "UNKNOWN",
});

function warningTitle(code: string): string {
  if (code.includes("HIGH_RISK") || code.includes("REVIEW")) return "请先人工复核";
  return "请留意";
}

function limitationTitle(notice: CoachNotice): string {
  const code = notice.code;
  const detail = notice.message;
  if (code.includes("MODEL") || code.includes("PROVIDER")) return "模型解释限制";
  if (code.includes("CONTEXT") || code.includes("TRIMMED")) return "上下文已裁剪";
  if (code === "DATA_QUALITY_IS_COMPLETENESS") return "分析范围受限";
  if (code === "STRUCTURED_SEGMENTS_UNAVAILABLE") return "分析范围受限";
  if (code === "RUNNER_STATE_LIMITATION") {
    if (detail.includes("disabled") || detail.includes("not_defined") || detail.includes("当前版本")) return "当前能力限制";
    return "分析范围受限";
  }
  if (code.includes("RULE_DISABLED") || code.includes("NOT_DEFINED") || code.includes("CAPABILITY")) return "当前能力限制";
  if (code.includes("RPE_INCOMPLETE") || code.includes("PHASE_UNAVAILABLE") || code.includes("SEGMENT") || code.includes("COVERAGE")) return "分析范围受限";
  if (code.includes("TOOL")) return "部分数据不可用";
  if (code.includes("DATA") || code.includes("UNKNOWN")) return "数据不足";
  return "适用范围说明";
}

const NOTICE_CODE_LABELS: Record<string, string> = {
  AGENT_INVALID_REQUEST: "教练请求格式无效。",
  AGENT_UNKNOWN_INTENT: "当前不支持该教练请求类型。",
  AGENT_TOOL_NOT_FOUND: "请求所需的数据工具暂不可用。",
  AGENT_TOOL_NOT_ALLOWED: "当前请求不允许执行该操作。",
  AGENT_TOOL_ARGUMENTS_INVALID: "数据工具参数无效。",
  AGENT_TOOL_EXECUTION_FAILED: "数据工具未能返回通过校验的结果。",
  AGENT_MODEL_OUTPUT_INVALID: "模型返回的结构化结果无效。",
  AGENT_MODEL_FAILED: "模型服务未能完成本次请求。",
  AGENT_PROVIDER_DISABLED: "模型解释功能当前未启用。",
  AGENT_PROVIDER_UNCONFIGURED: "模型解释服务尚未完成配置。",
  AGENT_PROVIDER_UNAVAILABLE: "模型解释服务暂时不可用。",
  AGENT_PROVIDER_RATE_LIMITED: "模型解释请求过于频繁，请稍后再试。",
  AGENT_VALIDATION_FAILED: "模型回答未通过安全校验。",
  AGENT_CALL_LIMIT_EXCEEDED: "本次教练请求已达到调用次数上限。",
  AGENT_INTERNAL_ERROR: "教练服务未能安全完成本次请求。",
};

function noticeMessage(notice: CoachNotice): string {
  return NOTICE_CODE_LABELS[notice.code] ?? limitationMessage(notice.message);
}
</script>

<style scoped>
.notice-stack { display: grid; gap: 12px; }
.warning-panel, .limitation-panel { min-width: 0; padding: 16px; border-radius: var(--card-radius); }
.warning-panel { border: 1px solid #e8b9b4; background: #fff7f6; }
.limitation-panel { border: 1px solid #d8e2ec; background: #f8fafc; }
h2 { margin: 0; color: #26354a; font-size: 16px; }
ul { display: grid; gap: 10px; margin: 12px 0 0; padding: 0; list-style: none; }
li { display: grid; gap: 3px; min-width: 0; }
strong { color: #344054; font-size: 13px; }
span { overflow-wrap: anywhere; color: #475467; font-size: 13px; line-height: 1.6; }
</style>
