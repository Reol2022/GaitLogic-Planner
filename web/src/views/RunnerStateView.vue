<template>
  <div class="page-stack runner-state-page">
    <PageHeader title="训练状态" :subtitle="headerSubtitle">
      <template #actions>
        <el-popover placement="bottom-end" :width="320" trigger="click">
          <template #reference>
            <el-button :icon="InfoFilled">说明</el-button>
          </template>
          <strong>训练管理辅助说明</strong>
          <p class="medical-note">本页面用于整理训练数据和训练压力信号，不构成医疗诊断、伤病判断或治疗建议。</p>
        </el-popover>
        <el-button
          class="refresh-button"
          type="primary"
          :icon="Refresh"
          :loading="loading"
          :disabled="loading"
          @click="loadState(true)"
        >刷新</el-button>
      </template>
    </PageHeader>

    <div v-if="loading && !snapshot" class="loading-shell" aria-label="训练状态加载中">
      <el-skeleton :rows="8" animated />
    </div>

    <el-result v-else-if="error && !snapshot" icon="error" title="训练状态加载失败" :sub-title="error">
      <template #extra><el-button type="primary" :disabled="loading" @click="loadState(false)">重新加载</el-button></template>
    </el-result>

    <template v-else-if="snapshot">
      <el-alert v-if="error" class="refresh-error" type="warning" :closable="false" show-icon>
        <template #title>刷新失败，当前仍显示上一次成功加载的状态。</template>
      </el-alert>

      <RunnerStateSummary :summary="summary" />

      <section class="state-card-grid" aria-label="当前训练状态">
        <RunnerStateCard
          title="跑量趋势"
          :icon="TrendCharts"
          :display="volumeDisplay"
          :details="volumeDetails"
          :evidence="snapshot.volume_trend?.evidence"
          :reason-codes="snapshot.volume_trend?.reason_codes"
          :ruleset-version="snapshot.volume_trend?.ruleset_version"
        />
        <RunnerStateCard
          title="训练一致性"
          :icon="CircleCheck"
          :display="consistencyStateDisplay"
          :details="consistencyDetails"
          :evidence="snapshot.training_consistency?.evidence"
          :reason-codes="snapshot.training_consistency?.reason_codes"
          :ruleset-version="snapshot.training_consistency?.ruleset_version"
          :evidence-coverage="snapshot.training_consistency?.evidence_coverage"
        />
        <RunnerStateCard
          title="疲劳信号"
          :icon="Warning"
          :display="fatigueStateDisplay"
          :details="fatigueDetails"
          :evidence="snapshot.fatigue?.evidence"
          :skipped-signals="snapshot.fatigue?.skipped_signals"
          :reason-codes="snapshot.fatigue?.reason_codes"
          :ruleset-version="snapshot.fatigue?.ruleset_version"
          :evidence-coverage="snapshot.fatigue?.evidence_coverage"
        />
        <RunnerStateCard
          title="训练阶段"
          :icon="Flag"
          :display="phaseStateDisplay"
          :details="phaseDetails"
          :reason-codes="phaseReasonCodes"
          :ruleset-version="snapshot.inference_metadata?.ruleset_version"
        />
      </section>

      <RunnerStateRiskList :flags="snapshot.risk_flags" :ruleset-version="snapshot.inference_metadata?.ruleset_version" />
      <RunnerStateMetrics :snapshot="snapshot" />
      <RunnerStateDataQuality
        :quality="snapshot.data_quality"
        :inference-limitations="snapshot.inference_metadata?.limitations"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { CircleCheck, Flag, InfoFilled, Refresh, TrendCharts, Warning } from "@element-plus/icons-vue";
import { getCurrentRunnerState } from "@/api/runnerState";
import RunnerStateCard from "@/components/runner-state/RunnerStateCard.vue";
import RunnerStateDataQuality from "@/components/runner-state/RunnerStateDataQuality.vue";
import RunnerStateMetrics from "@/components/runner-state/RunnerStateMetrics.vue";
import RunnerStateRiskList from "@/components/runner-state/RunnerStateRiskList.vue";
import RunnerStateSummary from "@/components/runner-state/RunnerStateSummary.vue";
import type { RunnerStateSnapshot } from "@/types/runnerState";
import {
  consistencyDisplay,
  fatigueDisplay,
  inferenceBasisLabels,
  trainingPhaseDisplay,
  volumeTrendDisplay,
} from "@/utils/runnerStateDisplay";
import { formatDate, formatDateTime, formatDistance, formatPercent, formatRatio } from "@/utils/runnerStateFormat";
import { buildRunnerStateSummary } from "@/utils/runnerStateSummary";
import { getRequestErrorMessage } from "@/api/request";

const snapshot = ref<RunnerStateSnapshot | null>(null);
const loading = ref(false);
const error = ref("");

const headerSubtitle = computed(() => snapshot.value
  ? `数据截止 ${formatDate(snapshot.value.identity.calculation_window_end)} · 最近计算 ${formatDateTime(snapshot.value.inference_metadata?.calculated_at || snapshot.value.identity.generated_at)}`
  : "查看当前跑量、训练执行和训练压力信号。"
);
const summary = computed(() => buildRunnerStateSummary(snapshot.value!));
const volumeState = computed(() => snapshot.value?.volume_trend?.state ?? "UNKNOWN");
const consistencyState = computed(() => snapshot.value?.training_consistency?.state ?? snapshot.value?.inferred_state.training_consistency ?? "UNKNOWN");
const fatigueState = computed(() => snapshot.value?.fatigue?.state ?? snapshot.value?.inferred_state.fatigue_state ?? "UNKNOWN");
const phaseState = computed(() => snapshot.value?.inferred_state.training_phase ?? "UNKNOWN");
const volumeDisplay = computed(() => volumeTrendDisplay[volumeState.value]);
const consistencyStateDisplay = computed(() => consistencyDisplay[consistencyState.value]);
const fatigueStateDisplay = computed(() => fatigueDisplay[fatigueState.value]);
const phaseStateDisplay = computed(() => trainingPhaseDisplay[phaseState.value]);

const volumeDetails = computed(() => [
  { label: "最近 7 天跑量", value: formatDistance(snapshot.value?.recent_training.distance_7d_km) },
  { label: "此前 21 天周均", value: formatDistance(snapshot.value?.volume_trend?.previous_21d_weekly_average_km) },
  { label: "变化比例", value: formatRatio(snapshot.value?.volume_trend?.volume_ratio) },
]);
const consistencyDetails = computed(() => [
  {
    label: "判断依据",
    value: snapshot.value?.training_consistency?.basis
      ? inferenceBasisLabels[snapshot.value.training_consistency.basis]
      : "暂无数据",
  },
  { label: "28 天计划完成率", value: formatPercent(snapshot.value?.recent_training.completion_rate_28d) },
]);
const fatigueDetails = computed(() => [
  { label: "可用信号", value: snapshot.value?.fatigue ? `${snapshot.value.fatigue.available_signal_count}/${snapshot.value.fatigue.total_signal_count}` : "暂无数据" },
  { label: "证据覆盖程度", value: formatPercent(snapshot.value?.fatigue?.evidence_coverage) },
]);
const phaseDetails = computed(() => [
  { label: "阶段来源", value: phaseState.value === "UNKNOWN" ? "当前没有结构化阶段" : "训练周期结构化字段" },
]);
const phaseReasonCodes = computed(() => snapshot.value?.inference_metadata?.reason_codes.filter((code) => code === "TRAINING_PHASE_UNAVAILABLE") ?? []);

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

onMounted(() => loadState(false));
</script>

<style scoped>
.runner-state-page { gap: 16px; }
.medical-note { margin: 8px 0 0; color: var(--muted); line-height: 1.65; }
.loading-shell { padding: 22px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; }
.refresh-error { flex: 0 0 auto; }
.state-card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }

@media (max-width: 900px) {
  .state-card-grid { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .runner-state-page { padding-bottom: 88px; }
  :deep(.app-page-header__actions) { display: grid; grid-template-columns: 1fr 1fr; }
  :deep(.app-page-header__actions .el-button) { width: 100%; min-height: 44px; margin-left: 0; }
}

@media (max-width: 420px) {
  :deep(.app-page-header__actions) { grid-template-columns: 1fr; }
}
</style>
