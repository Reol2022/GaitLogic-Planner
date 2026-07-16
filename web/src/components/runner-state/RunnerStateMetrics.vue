<template>
  <section class="metrics-section" aria-labelledby="runner-metrics-title">
    <div class="section-heading">
      <span>训练记录</span>
      <h2 id="runner-metrics-title">核心指标</h2>
    </div>
    <div class="metrics-groups">
      <article class="metrics-group">
        <h3>最近 7 天</h3>
        <div class="metric-grid-local">
          <div v-for="item in recentItems" :key="item.label" class="metric-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
      <article class="metrics-group">
        <h3>最近 28 天</h3>
        <div class="metric-grid-local">
          <div v-for="item in monthlyItems" :key="item.label" class="metric-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RunnerStateSnapshot } from "@/types/runnerState";
import { formatCount, formatDistance, formatMinutes, formatPercent, formatRpe } from "@/utils/runnerStateFormat";

const props = defineProps<{ snapshot: RunnerStateSnapshot }>();

const recentItems = computed(() => [
  { label: "总跑量", value: formatDistance(props.snapshot.recent_training.distance_7d_km) },
  { label: "总训练时长", value: formatMinutes(props.snapshot.recent_training.duration_7d_minutes) },
  { label: "训练次数", value: formatCount(props.snapshot.recent_training.sessions_7d) },
  { label: "高强度次数", value: formatCount(props.snapshot.derived_metrics?.high_intensity_sessions_7d) },
  { label: "平均 RPE", value: formatRpe(props.snapshot.recent_training.average_rpe_7d) },
  { label: "计划完成率", value: formatPercent(props.snapshot.recent_training.completion_rate_7d) },
]);

const monthlyItems = computed(() => [
  { label: "总跑量", value: formatDistance(props.snapshot.recent_training.distance_28d_km) },
  {
    label: "周均跑量",
    value: formatDistance(
      props.snapshot.recent_training.distance_28d_km === null || props.snapshot.recent_training.distance_28d_km === undefined
        ? null
        : props.snapshot.recent_training.distance_28d_km / 4,
    ),
  },
  { label: "训练次数", value: formatCount(props.snapshot.recent_training.sessions_28d) },
  { label: "活跃 7 日桶", value: formatCount(props.snapshot.derived_metrics?.active_weeks_28d, "个") },
  { label: "关键课次数", value: formatCount(props.snapshot.intensity.quality_sessions_28d) },
  { label: "高强度距离比例", value: formatPercent(props.snapshot.intensity.hard_distance_ratio_28d) },
  { label: "计划完成率", value: formatPercent(props.snapshot.recent_training.completion_rate_28d) },
]);
</script>

<style scoped>
.metrics-section { padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
.section-heading span { color: #1976d2; font-size: 12px; font-weight: 700; }
.section-heading h2 { margin: 4px 0 0; font-size: 19px; }
.metrics-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }
.metrics-group { min-width: 0; padding: 14px; border: 1px solid var(--line-soft); border-radius: 6px; background: #fbfcfd; }
.metrics-group h3 { margin: 0 0 12px; color: #344054; font-size: 15px; }
.metric-grid-local { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.metric-item { min-width: 0; padding: 10px; border-radius: 5px; background: #fff; }
.metric-item span { display: block; color: var(--muted); font-size: 11px; }
.metric-item strong { display: block; margin-top: 5px; overflow-wrap: anywhere; color: #1f4e79; font-size: 16px; }

@media (max-width: 900px) { .metrics-groups { grid-template-columns: 1fr; } }
@media (max-width: 420px) { .metric-grid-local { grid-template-columns: 1fr; } }
</style>
