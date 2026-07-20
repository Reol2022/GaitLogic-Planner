<template>
  <div class="snapshot-content">
    <RunnerStateSummary :summary="summary" />
    <section class="state-card-grid" aria-label="训练状态">
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
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { CircleCheck, Flag, TrendCharts, Warning } from "@element-plus/icons-vue";
import RunnerStateCard from "./RunnerStateCard.vue";
import RunnerStateDataQuality from "./RunnerStateDataQuality.vue";
import RunnerStateMetrics from "./RunnerStateMetrics.vue";
import RunnerStateRiskList from "./RunnerStateRiskList.vue";
import RunnerStateSummary from "./RunnerStateSummary.vue";
import type { RunnerStateSnapshot } from "@/types/runnerState";
import {
  consistencyDisplay,
  fatigueDisplay,
  inferenceBasisLabels,
  trainingPhaseDisplay,
  volumeTrendDisplay,
} from "@/utils/runnerStateDisplay";
import { formatDistance, formatPercent, formatRatio } from "@/utils/runnerStateFormat";
import { buildRunnerStateSummary } from "@/utils/runnerStateSummary";

const props = defineProps<{ snapshot: RunnerStateSnapshot }>();
const summary = computed(() => buildRunnerStateSummary(props.snapshot));
const volumeState = computed(() => props.snapshot.volume_trend?.state ?? "UNKNOWN");
const consistencyState = computed(() => props.snapshot.training_consistency?.state ?? props.snapshot.inferred_state.training_consistency ?? "UNKNOWN");
const fatigueState = computed(() => props.snapshot.fatigue?.state ?? props.snapshot.inferred_state.fatigue_state ?? "UNKNOWN");
const phaseState = computed(() => props.snapshot.inferred_state.training_phase ?? "UNKNOWN");
const volumeDisplay = computed(() => volumeTrendDisplay[volumeState.value]);
const consistencyStateDisplay = computed(() => consistencyDisplay[consistencyState.value]);
const fatigueStateDisplay = computed(() => fatigueDisplay[fatigueState.value]);
const phaseStateDisplay = computed(() => trainingPhaseDisplay[phaseState.value]);
const volumeDetails = computed(() => [
  { label: "最近 7 天跑量", value: formatDistance(props.snapshot.recent_training.distance_7d_km) },
  { label: "此前 21 天周均", value: formatDistance(props.snapshot.volume_trend?.previous_21d_weekly_average_km) },
  { label: "变化比例", value: formatRatio(props.snapshot.volume_trend?.volume_ratio) },
]);
const consistencyDetails = computed(() => [
  {
    label: "判断依据",
    value: props.snapshot.training_consistency?.basis
      ? inferenceBasisLabels[props.snapshot.training_consistency.basis]
      : "暂无数据",
  },
  { label: "28 天计划完成率", value: formatPercent(props.snapshot.recent_training.completion_rate_28d) },
]);
const fatigueDetails = computed(() => [
  {
    label: "可用信号",
    value: props.snapshot.fatigue
      ? `${props.snapshot.fatigue.available_signal_count}/${props.snapshot.fatigue.total_signal_count}`
      : "暂无数据",
  },
  { label: "证据覆盖程度", value: formatPercent(props.snapshot.fatigue?.evidence_coverage) },
]);
const phaseDetails = computed(() => [
  { label: "阶段来源", value: phaseState.value === "UNKNOWN" ? "当前没有结构化阶段" : "训练周期结构化字段" },
]);
const phaseReasonCodes = computed(() => props.snapshot.inference_metadata?.reason_codes.filter((code) => code === "TRAINING_PHASE_UNAVAILABLE") ?? []);
</script>

<style scoped>
.snapshot-content { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.state-card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
@media (max-width: 900px) { .state-card-grid { grid-template-columns: 1fr; } }
</style>
