<template>
  <div class="page-stack">
    <div class="toolbar">
      <el-select
        v-model="cycleId"
        clearable
        filterable
        placeholder="全部训练周期"
        style="width: 260px"
        @change="loadDashboard"
      >
        <el-option
          v-for="cycle in cycles"
          :key="cycle.id"
          :label="cycle.name"
          :value="cycle.id"
        />
      </el-select>
      <el-button :icon="Refresh" @click="loadDashboard">刷新</el-button>
    </div>

    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-label">计划 km</div>
        <div class="metric-value">{{ fmt(summary?.planned_distance_km) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">实际 km</div>
        <div class="metric-value">{{ fmt(summary?.actual_distance_km) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">完成率</div>
        <div class="metric-value">{{ fmt(summary?.completion_rate) }}%</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">训练次数</div>
        <div class="metric-value">{{ summary?.workout_count ?? 0 }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">平均 RPE</div>
        <div class="metric-value">{{ fmt(summary?.avg_rpe) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">最高疼痛等级</div>
        <div class="metric-value">{{ summary?.max_pain_level ?? "-" }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <h2 class="panel-title">主类型分布</h2>
      </div>
      <div ref="chartRef" class="chart"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import * as echarts from "echarts";

import { getDashboard } from "@/api/dashboard";
import { listTrainingCycles } from "@/api/trainingCycles";
import type { DashboardSummary, TrainingCycle } from "@/types/models";

const cycleId = ref<number | null>(null);
const cycles = ref<TrainingCycle[]>([]);
const summary = ref<DashboardSummary | null>(null);
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

function fmt(value?: number | string | null) {
  if (value === undefined || value === null || value === "") return "0";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : String(value);
}

function renderChart() {
  if (!chartRef.value || !summary.value) return;
  chart ||= echarts.init(chartRef.value);
  const entries = Object.entries(summary.value.main_type_distribution || {});
  chart.setOption({
    color: ["#2f806b", "#79d8b4", "#f0b45b", "#627a92", "#c95f5f", "#8a74d6"],
    tooltip: { trigger: "item" },
    grid: { left: 40, right: 20, top: 20, bottom: 34 },
    xAxis: { type: "category", data: entries.map(([key]) => key) },
    yAxis: { type: "value", minInterval: 1 },
    series: [
      {
        type: "bar",
        data: entries.map(([, value]) => value),
        barMaxWidth: 42,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
    ],
  });
}

async function loadDashboard() {
  summary.value = await getDashboard(cycleId.value);
  await nextTick();
  renderChart();
}

async function loadCycles() {
  cycles.value = await listTrainingCycles();
}

function resizeChart() {
  chart?.resize();
}

onMounted(async () => {
  await loadCycles();
  await loadDashboard();
  window.addEventListener("resize", resizeChart);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
});
</script>

<style scoped>
.chart {
  width: 100%;
  height: 340px;
}
</style>

