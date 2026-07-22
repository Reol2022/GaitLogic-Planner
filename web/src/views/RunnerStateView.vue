<template>
  <div class="page-stack runner-state-page">
    <PageHeader title="训练状态" :subtitle="headerSubtitle">
      <template #actions>
        <el-popover placement="bottom-end" :width="320" trigger="click">
          <template #reference><el-button :icon="InfoFilled">说明</el-button></template>
          <strong>训练管理辅助说明</strong>
          <p class="medical-note">本页面用于整理训练数据和训练压力信号，不构成医疗诊断、伤病判断或治疗建议。</p>
        </el-popover>
        <RunnerStateSaveButton :loading="saving" @save="saveSnapshot" />
        <el-button
          v-if="activeTab === 'current'"
          class="refresh-button"
          type="primary"
          :icon="Refresh"
          :loading="loading"
          :disabled="loading"
          @click="loadState(true)"
        >刷新状态</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab" class="runner-state-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="当前状态" name="current" />
      <el-tab-pane label="历史趋势" name="history" />
    </el-tabs>

    <template v-if="activeTab === 'current'">
      <div v-if="loading && !snapshot" class="loading-shell" aria-label="训练状态加载中">
        <el-skeleton :rows="8" animated />
      </div>
      <el-result v-else-if="error && !snapshot" icon="error" title="训练状态加载失败" :sub-title="error">
        <template #extra><el-button type="primary" :disabled="loading" @click="loadState(false)">重新加载</el-button></template>
      </el-result>
      <template v-else-if="snapshot">
        <el-alert v-if="error" class="refresh-error" type="warning" :closable="false" show-icon title="刷新失败，当前仍显示上一次成功加载的状态。" />
        <RunnerStateSnapshotContent :snapshot="snapshot" />
      </template>
    </template>

    <RunnerStateHistoryView
      v-if="historyMounted"
      v-show="activeTab === 'history'"
      ref="historyView"
      @return-current="activeTab = 'current'"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { InfoFilled, Refresh } from "@element-plus/icons-vue";
import { getCurrentRunnerState, saveCurrentRunnerStateSnapshot } from "@/api/runnerState";
import { getRequestErrorMessage } from "@/api/request";
import RunnerStateHistoryView from "@/components/runner-state/RunnerStateHistoryView.vue";
import RunnerStateSaveButton from "@/components/runner-state/RunnerStateSaveButton.vue";
import RunnerStateSnapshotContent from "@/components/runner-state/RunnerStateSnapshotContent.vue";
import type { RunnerStateSnapshot } from "@/types/runnerState";
import { formatDate, formatDateTime } from "@/utils/runnerStateFormat";

const snapshot = ref<RunnerStateSnapshot | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const activeTab = ref<"current" | "history">("current");
const historyMounted = ref(false);
const historyView = ref<InstanceType<typeof RunnerStateHistoryView> | null>(null);

const headerSubtitle = computed(() => snapshot.value
  ? `数据截止 ${formatDate(snapshot.value.identity.calculation_window_end)} · 最近计算 ${formatDateTime(snapshot.value.inference_metadata?.calculated_at || snapshot.value.identity.generated_at)}`
  : "查看当前跑量、训练执行和训练压力信号。"
);

async function loadState(manual: boolean) {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const response = await getCurrentRunnerState();
    snapshot.value = response.snapshot;
    if (manual) ElMessage.success("训练状态已刷新");
  } catch (requestError) {
    error.value = getRequestErrorMessage(requestError);
    if (manual) ElMessage.error(`刷新失败：${error.value}`);
  } finally {
    loading.value = false;
  }
}

async function saveSnapshot() {
  if (saving.value) return;
  saving.value = true;
  try {
    const result = await saveCurrentRunnerStateSnapshot();
    if (result.duplicate) {
      ElMessage.info("当前状态与最近保存记录一致，无需重复保存");
    } else {
      ElMessage.success("今日训练状态已保存");
    }
    if (historyMounted.value) {
      await nextTick();
      await historyView.value?.refresh();
    }
  } catch (requestError) {
    ElMessage.error(`保存失败：${getRequestErrorMessage(requestError)}`);
  } finally {
    saving.value = false;
  }
}

function handleTabChange(name: string | number) {
  if (name === "history") historyMounted.value = true;
}

onMounted(() => loadState(false));
</script>

<style scoped>
.runner-state-page { gap: 16px; }
.medical-note { margin: 8px 0 0; color: var(--muted); line-height: 1.65; }
.loading-shell { padding: 22px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; }
.refresh-error { flex: 0 0 auto; }
.runner-state-tabs { padding: 0 4px; border-bottom: 1px solid var(--line-soft); }

@media (max-width: 768px) {
  .runner-state-page { padding-bottom: 88px; }
  :deep(.app-page-header__actions) { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  :deep(.app-page-header__actions .el-button) { width: 100%; min-height: 44px; margin-left: 0; }
}
@media (max-width: 520px) { :deep(.app-page-header__actions) { grid-template-columns: 1fr 1fr; } }
@media (max-width: 340px) { :deep(.app-page-header__actions) { grid-template-columns: 1fr; } }
</style>
