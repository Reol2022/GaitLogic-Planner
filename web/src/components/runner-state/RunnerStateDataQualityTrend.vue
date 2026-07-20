<template>
  <section class="history-card" aria-labelledby="quality-trend-title">
    <h2 id="quality-trend-title">数据质量变化</h2>
    <p class="section-note">这些数值仅表示数据覆盖情况，不表示状态判断表现或风险概率。</p>
    <div v-if="items.length" class="quality-table-wrap">
      <table><thead><tr><th>截止日期</th><th>数据完整度</th><th>证据覆盖程度</th><th>RPE 数据覆盖率</th><th>心率数据覆盖率</th></tr></thead>
      <tbody><tr v-for="item in items" :key="item.id"><td>{{ formatDate(item.data_cutoff_date) }}</td><td>{{ formatPercent(item.data_completeness) }}</td><td>{{ formatPercent(item.evidence_coverage) }}</td><td>{{ formatPercent(item.rpe_coverage_28d) }}</td><td>{{ formatPercent(item.heart_rate_coverage_28d) }}</td></tr></tbody></table>
    </div>
    <el-empty v-else :image-size="60" description="当前范围没有数据质量记录" />
  </section>
</template>

<script setup lang="ts">
import type { RunnerStateTimelineItem } from "@/types/runnerState";
import { formatDate, formatPercent } from "@/utils/runnerStateFormat";
defineProps<{ items: RunnerStateTimelineItem[] }>();
</script>

<style scoped>
.history-card { min-width: 0; padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
h2 { margin: 0; color: #172033; font-size: 18px; }.section-note { margin: 6px 0 16px; color: var(--muted); font-size: 12px; }
.quality-table-wrap { overflow-x: auto; } table { width: 100%; min-width: 660px; border-collapse: collapse; font-size: 13px; } th, td { padding: 10px; border-bottom: 1px solid var(--line-soft); text-align: left; } th { color: #344054; background: #f8fafc; } td { color: #475467; }
@media (max-width: 680px) { .history-card { padding: 14px; } }
</style>
