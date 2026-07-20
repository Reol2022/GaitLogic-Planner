<template>
  <section class="history-summary" aria-labelledby="history-summary-title">
    <div>
      <span class="eyebrow">历史摘要</span>
      <h2 id="history-summary-title">{{ summary.title }}</h2>
      <p>{{ summary.recordLine }}</p>
      <p>{{ summary.latestLine }}</p>
    </div>
    <dl>
      <div><dt>最近快照</dt><dd>{{ latestDate }}</dd></div>
      <div><dt>最近保存</dt><dd>{{ latestSavedAt }}</dd></div>
      <div><dt>提示出现天数</dt><dd>{{ summary.riskDays }} 天</dd></div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RunnerStateTimelineResponse } from "@/types/runnerState";
import { buildHistorySummary } from "@/utils/runnerStateHistory";
import { formatDate, formatDateTime } from "@/utils/runnerStateFormat";

const props = defineProps<{ timeline: RunnerStateTimelineResponse }>();
const summary = computed(() => buildHistorySummary(props.timeline));
const latestDate = computed(() => formatDate(props.timeline.items[props.timeline.items.length - 1]?.data_cutoff_date));
const latestSavedAt = computed(() => formatDateTime(props.timeline.items[props.timeline.items.length - 1]?.created_at));
</script>

<style scoped>
.history-summary { display: flex; justify-content: space-between; gap: 24px; padding: 20px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: linear-gradient(135deg, #f7fbff, #fff); box-shadow: var(--card-shadow); }
.eyebrow { color: #1976d2; font-size: 12px; font-weight: 700; }
h2 { margin: 5px 0 10px; color: #172033; font-size: 22px; }
p { margin: 4px 0; color: var(--muted); line-height: 1.55; }
dl { display: grid; grid-template-columns: repeat(2, minmax(120px, 1fr)); gap: 10px; margin: 0; }
dl div { padding: 12px; border-radius: 8px; background: #fff; }
dt { color: var(--muted); font-size: 12px; }
dd { margin: 6px 0 0; color: #1f4e79; font-size: 18px; font-weight: 700; }
@media (max-width: 680px) { .history-summary { flex-direction: column; padding: 16px; } dl { grid-template-columns: 1fr 1fr; } }
</style>
