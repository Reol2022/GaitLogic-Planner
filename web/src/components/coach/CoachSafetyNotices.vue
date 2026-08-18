<template>
  <section v-if="warnings.length || limitations.length" class="notice-stack" aria-label="建议提示和限制">
    <div v-if="warnings.length" class="warning-panel" role="alert">
      <h2>{{ riskLevel === "HIGH" ? "需要重点关注" : "训练提示" }}</h2>
      <ul>
        <li v-for="notice in warnings" :key="`${notice.code}-${notice.message}`">
          <strong>{{ warningTitle(notice.code) }}</strong>
          <span>{{ notice.message }}</span>
        </li>
      </ul>
    </div>
    <div v-if="limitations.length" class="limitation-panel" role="status">
      <h2>结论限制</h2>
      <ul>
        <li v-for="notice in limitations" :key="`${notice.code}-${notice.message}`">
          <strong>{{ limitationTitle(notice.code) }}</strong>
          <span>{{ notice.message }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { CoachNotice, CoachRiskLevel } from "@/types/coachAgent";

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

function limitationTitle(code: string): string {
  if (code.includes("MODEL") || code.includes("PROVIDER")) return "模型解释限制";
  if (code.includes("CONTEXT") || code.includes("TRIMMED")) return "上下文已裁剪";
  if (code.includes("RULE_DISABLED") || code.includes("NOT_DEFINED") || code.includes("CAPABILITY")) return "当前能力限制";
  if (code.includes("RPE_INCOMPLETE") || code.includes("PHASE_UNAVAILABLE") || code.includes("SEGMENT") || code.includes("COVERAGE")) return "分析范围受限";
  if (code.includes("TOOL")) return "部分数据不可用";
  if (code.includes("DATA") || code.includes("UNKNOWN")) return "数据不足";
  return "适用范围说明";
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
