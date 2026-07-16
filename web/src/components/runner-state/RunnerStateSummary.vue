<template>
  <section class="runner-summary" :class="`tone-${summary.tone}`" aria-labelledby="runner-state-summary-title">
    <el-icon class="summary-icon"><component :is="icon" /></el-icon>
    <div>
      <span class="summary-kicker">综合摘要</span>
      <h2 id="runner-state-summary-title">{{ summary.title }}</h2>
      <p>{{ summary.body }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { CircleCheck, InfoFilled, TrendCharts, Warning } from "@element-plus/icons-vue";
import type { RunnerStateSummaryCopy } from "@/utils/runnerStateSummary";

const props = defineProps<{ summary: RunnerStateSummaryCopy }>();

const icon = computed(() => ({
  positive: CircleCheck,
  notice: TrendCharts,
  attention: Warning,
  neutral: InfoFilled,
})[props.summary.tone]);
</script>

<style scoped>
.runner-summary {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  padding: 20px;
  border: 1px solid var(--card-border);
  border-left: 4px solid #8293a4;
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.runner-summary.tone-positive { border-left-color: var(--success); }
.runner-summary.tone-notice { border-left-color: var(--accent); }
.runner-summary.tone-attention { border-left-color: #b35b46; }

.summary-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  color: #1f4e79;
  background: var(--blue-soft);
  font-size: 24px;
}

.summary-kicker { color: var(--muted); font-size: 12px; font-weight: 700; }
h2 { margin: 4px 0 0; color: #172033; font-size: 22px; }
p { margin: 8px 0 0; color: var(--muted); line-height: 1.7; }

@media (max-width: 520px) {
  .runner-summary { grid-template-columns: 36px minmax(0, 1fr); padding: 16px; }
  .summary-icon { width: 36px; height: 36px; font-size: 20px; }
  h2 { font-size: 18px; }
}
</style>
