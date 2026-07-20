<template>
  <section class="history-card" aria-labelledby="snapshot-list-title">
    <header><div><h2 id="snapshot-list-title">快照记录</h2><p>保留同日全部保存版本，最新保存时间排在前面。</p></div><span>{{ response?.total ?? 0 }} 条</span></header>
    <el-alert v-if="error" type="warning" :closable="false" show-icon :title="error" />
    <div v-if="loading && !response" class="list-loading"><el-skeleton :rows="4" animated /></div>
    <div v-else-if="response?.items.length" class="snapshot-list">
      <article v-for="item in response.items" :key="item.id">
        <div class="snapshot-date"><strong>{{ formatDate(item.data_cutoff_date) }}</strong><span>{{ formatDateTime(item.created_at) }}</span></div>
        <div class="snapshot-tags">
          <el-tag type="info">{{ snapshotTriggerLabels[item.trigger_type] }}</el-tag>
          <el-tag>{{ volumeTrendDisplay[item.volume_trend ?? 'UNKNOWN'].label }}</el-tag>
          <el-tag>{{ consistencyDisplay[item.training_consistency ?? 'UNKNOWN'].label }}</el-tag>
          <el-tag>{{ fatigueDisplay[item.fatigue_state ?? 'UNKNOWN'].label }}</el-tag>
        </div>
        <div class="snapshot-meta"><span>{{ item.risk_flag_count }} 项提示</span><span>{{ item.ruleset_version }}</span></div>
        <el-button type="primary" plain @click="$emit('open-detail', item.id)">查看详情</el-button>
      </article>
      <el-pagination
        v-if="response.total > response.limit"
        class="snapshot-pagination"
        background
        layout="prev, pager, next"
        :page-size="response.limit"
        :current-page="currentPage"
        :total="response.total"
        @current-change="$emit('page-change', $event)"
      />
    </div>
    <el-empty v-else-if="!loading" :image-size="64" description="当前范围没有快照记录" />
  </section>
</template>

<script setup lang="ts">
import type { RunnerStateSnapshotListResponse } from "@/types/runnerState";
import { consistencyDisplay, fatigueDisplay, snapshotTriggerLabels, volumeTrendDisplay } from "@/utils/runnerStateDisplay";
import { formatDate, formatDateTime } from "@/utils/runnerStateFormat";
defineProps<{ response: RunnerStateSnapshotListResponse | null; currentPage: number; loading: boolean; error: string }>();
defineEmits<{ "open-detail": [snapshotId: number]; "page-change": [page: number] }>();
</script>

<style scoped>
.history-card { min-width: 0; padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
header { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 14px; } h2 { margin: 0; color: #172033; font-size: 18px; } header p { margin: 5px 0 0; color: var(--muted); font-size: 12px; } header > span { color: #1976d2; font-weight: 700; }
.snapshot-list { display: grid; gap: 9px; } article { display: grid; grid-template-columns: minmax(150px, .8fr) minmax(260px, 1.5fr) minmax(180px, 1fr) auto; gap: 12px; align-items: center; padding: 13px; border: 1px solid var(--line-soft); border-radius: 8px; }
.snapshot-date { display: flex; flex-direction: column; gap: 3px; }.snapshot-date span, .snapshot-meta { color: var(--muted); font-size: 12px; }.snapshot-tags { display: flex; flex-wrap: wrap; gap: 6px; }.snapshot-meta { display: flex; flex-direction: column; gap: 4px; overflow-wrap: anywhere; }
.snapshot-pagination { justify-content: center; margin-top: 10px; }.list-loading { padding: 10px; }
@media (max-width: 900px) { article { grid-template-columns: 1fr auto; } .snapshot-tags, .snapshot-meta { grid-column: 1 / -1; } }
@media (max-width: 520px) { .history-card { padding: 14px; } article { grid-template-columns: 1fr; } article .el-button { width: 100%; min-height: 44px; } .snapshot-tags, .snapshot-meta { grid-column: auto; } }
</style>
