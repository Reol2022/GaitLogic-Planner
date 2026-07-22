<template>
  <div v-if="result" class="snapshot-sync-status" :class="`is-${tone}`" role="status">
    <span class="status-dot" aria-hidden="true" />
    <div class="status-copy">
      <span>{{ message }}</span>
      <RouterLink v-if="result.status === 'CREATED'" to="/runner-state">
        查看训练状态
      </RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RunnerStateSnapshotSyncResult } from "@/types/models";

const props = defineProps<{
  result: RunnerStateSnapshotSyncResult | null | undefined;
}>();

const messages = {
  PROCESSING: "训练数据已同步，正在更新训练状态",
  CREATED: "训练状态历史已更新",
  DUPLICATE_PAYLOAD: "当前训练状态未发生变化，无需新增历史记录",
  SKIPPED_NO_MATERIAL_CHANGE: "本次同步未产生影响训练状态的新数据",
  SKIPPED_NOT_COMMITTED: "本次同步未提交训练数据，因此未更新训练状态",
  FAILED_NON_BLOCKING: "训练数据已同步，状态历史暂未更新",
} as const;

const message = computed(() => props.result ? messages[props.result.status] : "");
const tone = computed(() => {
  if (props.result?.status === "CREATED") return "success";
  if (props.result?.status === "FAILED_NON_BLOCKING") return "warning";
  return "neutral";
});
</script>

<style scoped>
.snapshot-sync-status {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: 100%;
  color: #475467;
  font-size: 12px;
  line-height: 1.45;
}

.status-dot {
  width: 7px;
  height: 7px;
  margin-top: 5px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #98a2b3;
}

.status-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
  overflow-wrap: anywhere;
}

.status-copy a {
  width: fit-content;
  color: var(--el-color-primary);
  text-decoration: none;
}

.is-success .status-dot {
  background: #12b76a;
}

.is-warning {
  color: #7a5a16;
}

.is-warning .status-dot {
  background: #f79009;
}

@media (max-width: 768px) {
  .snapshot-sync-status {
    font-size: 13px;
  }
}
</style>
