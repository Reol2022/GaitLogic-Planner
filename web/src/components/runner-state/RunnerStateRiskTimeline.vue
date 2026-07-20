<template>
  <section class="history-card" aria-labelledby="risk-timeline-title">
    <h2 id="risk-timeline-title">风险提示记录</h2>
    <p class="section-note">重复出现仅表示该提示在多个保存日期出现，不代表持续伤病风险。</p>
    <div v-if="events.length" class="risk-events">
      <article v-for="(event, index) in events" :key="`${event.snapshotId}-${event.flag.code}-${index}`" :class="`severity-${event.flag.severity.toLowerCase()}`">
        <div><time>{{ formatDate(event.date) }}</time><strong>{{ riskTitleLabels[event.flag.code] || event.flag.code }}</strong></div>
        <el-tag size="small" :type="event.flag.severity === 'ATTENTION' ? 'danger' : event.flag.severity === 'WARNING' ? 'warning' : 'info'">{{ severityLabels[event.flag.severity] }}</el-tag>
        <p>{{ event.flag.message }}</p>
        <el-button link type="primary" @click="$emit('open-detail', event.snapshotId)">查看快照详情</el-button>
      </article>
    </div>
    <el-empty v-else :image-size="60" description="当前范围没有风险提示记录" />
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RunnerStateTimelineItem } from "@/types/runnerState";
import { riskTitleLabels, severityLabels } from "@/utils/runnerStateDisplay";
import { formatDate } from "@/utils/runnerStateFormat";
import { buildRiskEvents } from "@/utils/runnerStateHistory";
const props = defineProps<{ items: RunnerStateTimelineItem[] }>();
defineEmits<{ "open-detail": [snapshotId: number] }>();
const events = computed(() => buildRiskEvents(props.items));
</script>

<style scoped>
.history-card { padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
h2 { margin: 0; color: #172033; font-size: 18px; }.section-note { margin: 6px 0 16px; color: var(--muted); font-size: 12px; }
.risk-events { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
article { min-width: 0; padding: 13px; border: 1px solid #e4e9ee; border-left: 4px solid #8293a4; border-radius: 8px; background: #fbfcfd; } article.severity-warning { border-left-color: #d59628; } article.severity-attention { border-left-color: #b35b46; }
article > div { display: flex; flex-direction: column; gap: 3px; } time { color: var(--muted); font-size: 12px; } strong { overflow-wrap: anywhere; color: #172033; }
article > .el-tag { margin-top: 8px; } article p { margin: 9px 0 4px; color: var(--muted); font-size: 13px; line-height: 1.55; }
@media (max-width: 680px) { .history-card { padding: 14px; } .risk-events { grid-template-columns: 1fr; } }
</style>
