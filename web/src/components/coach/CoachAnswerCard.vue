<template>
  <section class="answer-card" aria-labelledby="coach-answer-title">
    <div class="answer-heading">
      <div>
        <span>AI 解释</span>
        <h2 id="coach-answer-title">{{ statusDisplay.label }}</h2>
      </div>
      <time :datetime="generatedAt">{{ formattedTime }}</time>
    </div>

    <div v-if="status === 'DEGRADED'" class="degraded-notice" role="status">
      模型解释暂不可用，当前内容由系统规则和已有训练数据生成。
    </div>
    <p v-if="summary && canShowAnswer" class="summary">{{ summary }}</p>
    <p v-if="answer && canShowAnswer" class="answer-text">{{ answer }}</p>
    <p v-else-if="status === 'VALIDATION_FAILED'" class="safe-empty">
      模型内容未通过安全校验，因此未向你展示。
    </p>
    <p v-else-if="status === 'REJECTED'" class="safe-empty">该教练能力暂未开放。</p>
    <p v-else-if="status === 'UNAVAILABLE'" class="safe-empty">当前无法安全生成建议，请稍后重试。</p>

    <p class="provider-state">{{ coachProviderStatusDisplay[providerStatus] }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { CoachProviderStatus, CoachQueryStatus } from "@/types/coachAgent";
import { coachProviderStatusDisplay, coachStatusDisplay } from "@/utils/coachAgentDisplay";

const props = defineProps<{
  status: CoachQueryStatus;
  answer?: string | null;
  summary?: string | null;
  generatedAt: string;
  providerStatus: CoachProviderStatus;
}>();

const statusDisplay = computed(() => coachStatusDisplay[props.status]);
const canShowAnswer = computed(() => ["SUCCEEDED", "DEGRADED"].includes(props.status));
const formattedTime = computed(() => {
  const value = new Date(props.generatedAt);
  return Number.isNaN(value.getTime()) ? "时间未知" : value.toLocaleString("zh-CN", { hour12: false });
});
</script>

<style scoped>
.answer-card { min-width: 0; padding: 20px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
.answer-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.answer-heading span { color: #667085; font-size: 12px; }
.answer-heading h2 { margin: 4px 0 0; font-size: 18px; }
.answer-heading time { color: #7a8798; font-size: 12px; }
.degraded-notice { margin-top: 14px; padding: 11px 12px; border: 1px solid #efd8ba; border-radius: 6px; color: #80520d; background: #fff9ed; line-height: 1.55; }
.summary { margin: 15px 0 0; color: #26354a; font-weight: 700; line-height: 1.65; }
.answer-text { margin: 12px 0 0; overflow-wrap: anywhere; white-space: pre-wrap; color: #344054; line-height: 1.8; }
.safe-empty { margin: 15px 0 0; color: #475467; line-height: 1.7; }
.provider-state { margin: 15px 0 0; color: #667085; font-size: 12px; }
@media (max-width: 520px) {
  .answer-card { padding: 16px; }
  .answer-heading { flex-direction: column; }
}
</style>
