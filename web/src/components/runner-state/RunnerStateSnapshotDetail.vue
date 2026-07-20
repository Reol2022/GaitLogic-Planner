<template>
  <el-drawer
    :model-value="visible"
    class="snapshot-detail-drawer"
    title="历史快照详情"
    size="min(760px, 96vw)"
    append-to-body
    @update:model-value="$emit('update:visible', $event)"
  >
    <div v-if="loading" class="detail-loading"><el-skeleton :rows="8" animated /></div>
    <el-result v-else-if="error" icon="error" title="快照详情加载失败" :sub-title="error" />
    <div v-else-if="detail" class="detail-content">
      <el-alert type="info" :closable="false" show-icon title="这是当时保存的训练状态，不会根据当前训练数据重新计算。" />
      <dl class="detail-meta">
        <div><dt>截止日期</dt><dd>{{ formatDate(detail.data_cutoff_date) }}</dd></div>
        <div><dt>保存时间</dt><dd>{{ formatDateTime(detail.created_at) }}</dd></div>
        <div><dt>触发方式</dt><dd>{{ snapshotTriggerLabels[detail.trigger_type] }}</dd></div>
        <div><dt>规则版本</dt><dd>{{ detail.ruleset_version }}</dd></div>
        <div><dt>快照结构版本</dt><dd>{{ detail.snapshot_schema_version }}</dd></div>
      </dl>
      <RunnerStateSnapshotContent :snapshot="detail.snapshot_payload" />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import RunnerStateSnapshotContent from "./RunnerStateSnapshotContent.vue";
import type { RunnerStateSnapshotDetail } from "@/types/runnerState";
import { snapshotTriggerLabels } from "@/utils/runnerStateDisplay";
import { formatDate, formatDateTime } from "@/utils/runnerStateFormat";
defineProps<{ visible: boolean; detail: RunnerStateSnapshotDetail | null; loading: boolean; error: string }>();
defineEmits<{ "update:visible": [visible: boolean] }>();
</script>

<style scoped>
.detail-content { display: flex; flex-direction: column; gap: 16px; min-width: 0; }.detail-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; margin: 0; }.detail-meta div { min-width: 0; padding: 10px; border-radius: 7px; background: #f7f9fb; }.detail-meta dt { color: var(--muted); font-size: 12px; }.detail-meta dd { margin: 4px 0 0; overflow-wrap: anywhere; color: #344054; font-weight: 700; }
@media (max-width: 520px) { .detail-meta { grid-template-columns: 1fr; } }
</style>

<style>
@media (max-width: 520px) { .snapshot-detail-drawer { width: 100% !important; } .snapshot-detail-drawer .el-drawer__body { padding: 12px; } }
</style>
