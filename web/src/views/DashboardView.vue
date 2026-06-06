<template>
  <div class="dashboard-page">
    <section class="dashboard-hero">
      <div>
        <div class="hero-kicker">严飞夏训执行总览</div>
        <h2>{{ currentCycleName }}</h2>
        <p>训练计划、完成情况、强度结构和身体反馈的实时概览。</p>
      </div>
      <div class="hero-actions">
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
        <el-button :icon="Refresh" type="primary" @click="loadDashboard">刷新</el-button>
      </div>
    </section>

    <section class="metric-strip">
      <div class="metric-tile">
        <span>计划公里</span>
        <strong>{{ fmt(summary?.planned_distance_km) }}</strong>
        <em>planned km</em>
      </div>
      <div class="metric-tile">
        <span>实际公里</span>
        <strong>{{ fmt(summary?.actual_distance_km) }}</strong>
        <em>actual km</em>
      </div>
      <div class="metric-tile highlight">
        <span>完成率</span>
        <strong>{{ fmt(summary?.completion_rate) }}%</strong>
        <em>completion</em>
      </div>
      <div class="metric-tile">
        <span>训练次数</span>
        <strong>{{ summary?.workout_count ?? 0 }}</strong>
        <em>sessions</em>
      </div>
      <div class="metric-tile">
        <span>平均 RPE</span>
        <strong>{{ fmt(summary?.avg_rpe) }}</strong>
        <em>fatigue</em>
      </div>
      <div class="metric-tile pain">
        <span>最高疼痛</span>
        <strong>{{ summary?.max_pain_level ?? "-" }}</strong>
        <em>pain level</em>
      </div>
    </section>

    <section class="chart-grid">
      <article class="chart-card wide">
        <div class="chart-card-head">
          <div>
            <h3>计划 vs 实际公里</h3>
            <p>训练总量完成情况</p>
          </div>
          <span class="chart-badge">公里</span>
        </div>
        <div ref="distanceChartRef" class="chart"></div>
      </article>

      <article class="chart-card">
        <div class="chart-card-head">
          <div>
            <h3>训练类型分布</h3>
            <p>主类型占比</p>
          </div>
        </div>
        <div ref="typeChartRef" class="chart"></div>
      </article>

      <article class="chart-card">
        <div class="chart-card-head">
          <div>
            <h3>完成状态</h3>
            <p>完成、缺课与待完成</p>
          </div>
        </div>
        <div ref="statusChartRef" class="chart"></div>
      </article>

      <article class="chart-card wide">
        <div class="chart-card-head">
          <div>
            <h3>训练反馈雷达</h3>
            <p>完成率、RPE、疼痛等级综合查看</p>
          </div>
          <span class="chart-badge">反馈</span>
        </div>
        <div ref="healthChartRef" class="chart"></div>
      </article>
    </section>

    <section class="summary-table-card">
      <div class="chart-card-head">
        <div>
          <h3>执行摘要</h3>
          <p>与 Excel 总览页保持同一套指标口径</p>
        </div>
      </div>
      <table class="summary-table">
        <thead>
          <tr>
            <th>范围</th>
            <th>计划km</th>
            <th>实际km</th>
            <th>完成率</th>
            <th>训练次数</th>
            <th>完成</th>
            <th>缺课</th>
            <th>平均RPE</th>
            <th>最高疼痛</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{{ currentCycleName }}</td>
            <td>{{ fmt(summary?.planned_distance_km) }}</td>
            <td>{{ fmt(summary?.actual_distance_km) }}</td>
            <td>{{ fmt(summary?.completion_rate) }}%</td>
            <td>{{ summary?.workout_count ?? 0 }}</td>
            <td>{{ summary?.completed_count ?? 0 }}</td>
            <td>{{ summary?.missed_count ?? 0 }}</td>
            <td>{{ fmt(summary?.avg_rpe) }}</td>
            <td>{{ summary?.max_pain_level ?? "" }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import * as echarts from "echarts";

import { getDashboard } from "@/api/dashboard";
import { listTrainingCycles } from "@/api/trainingCycles";
import type { DashboardSummary, TrainingCycle } from "@/types/models";
import { labelFor, mainTypeOptions } from "@/types/options";

const cycleId = ref<number | null>(null);
const cycles = ref<TrainingCycle[]>([]);
const summary = ref<DashboardSummary | null>(null);

const distanceChartRef = ref<HTMLDivElement | null>(null);
const typeChartRef = ref<HTMLDivElement | null>(null);
const statusChartRef = ref<HTMLDivElement | null>(null);
const healthChartRef = ref<HTMLDivElement | null>(null);

let distanceChart: echarts.ECharts | null = null;
let typeChart: echarts.ECharts | null = null;
let statusChart: echarts.ECharts | null = null;
let healthChart: echarts.ECharts | null = null;

const palette = ["#1F4E79", "#5B9BD5", "#70AD47", "#F0B45B", "#C95F5F", "#8A74D6"];

const currentCycleName = computed(() => {
  if (!cycleId.value) return "全部周期";
  return cycles.value.find((cycle) => cycle.id === cycleId.value)?.name || "当前周期";
});

const translatedTypeRows = computed(() =>
  Object.entries(summary.value?.main_type_distribution || {}).map(([name, count]) => ({
    name: labelFor(mainTypeOptions, name as never),
    count,
  })),
);

const statusRows = computed(() => {
  const total = summary.value?.workout_count ?? 0;
  const done = summary.value?.completed_count ?? 0;
  const missed = summary.value?.missed_count ?? 0;
  const pending = Math.max(total - done - missed, 0);
  return [
    { name: "已完成", value: done },
    { name: "缺课", value: missed },
    { name: "待完成", value: pending },
  ];
});

function numeric(value?: number | string | null) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function fmt(value?: number | string | null) {
  const parsed = numeric(value);
  return parsed.toFixed(1);
}

function renderDistanceChart() {
  if (!distanceChartRef.value || !summary.value) return;
  distanceChart ||= echarts.init(distanceChartRef.value);
  distanceChart.setOption({
    color: ["#1F4E79", "#70AD47"],
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["计划公里", "实际公里"] },
    grid: { left: 44, right: 24, top: 48, bottom: 34 },
    xAxis: { type: "category", data: [currentCycleName.value], axisTick: { show: false } },
    yAxis: { type: "value", name: "km", splitLine: { lineStyle: { color: "#E4EDF5" } } },
    series: [
      {
        name: "计划公里",
        type: "bar",
        barWidth: 38,
        data: [numeric(summary.value.planned_distance_km)],
        itemStyle: { borderRadius: [5, 5, 0, 0] },
      },
      {
        name: "实际公里",
        type: "bar",
        barWidth: 38,
        data: [numeric(summary.value.actual_distance_km)],
        itemStyle: { borderRadius: [5, 5, 0, 0] },
      },
    ],
  });
}

function renderTypeChart() {
  if (!typeChartRef.value || !summary.value) return;
  typeChart ||= echarts.init(typeChartRef.value);
  const data = translatedTypeRows.value.map((row) => ({ name: row.name, value: row.count }));
  typeChart.setOption({
    color: palette,
    tooltip: { trigger: "item" },
    legend: { bottom: 0, type: "scroll" },
    series: [
      {
        name: "训练类型",
        type: "pie",
        radius: ["46%", "70%"],
        center: ["50%", "44%"],
        data,
        label: { formatter: "{b}" },
      },
    ],
  });
}

function renderStatusChart() {
  if (!statusChartRef.value || !summary.value) return;
  statusChart ||= echarts.init(statusChartRef.value);
  statusChart.setOption({
    color: ["#70AD47", "#C95F5F", "#5B9BD5"],
    tooltip: { trigger: "item" },
    legend: { bottom: 0, data: ["已完成", "缺课", "待完成"] },
    series: [
      {
        name: "完成状态",
        type: "pie",
        radius: "68%",
        center: ["50%", "44%"],
        data: statusRows.value,
        label: { formatter: "{b}: {c}" },
      },
    ],
  });
}

function renderHealthChart() {
  if (!healthChartRef.value || !summary.value) return;
  healthChart ||= echarts.init(healthChartRef.value);
  const completion = Math.min(numeric(summary.value.completion_rate), 100);
  const rpe = Math.min(numeric(summary.value.avg_rpe) * 10, 100);
  const pain = Math.min(numeric(summary.value.max_pain_level) * 20, 100);
  const doneRate =
    (summary.value.workout_count ?? 0) > 0
      ? ((summary.value.completed_count ?? 0) / (summary.value.workout_count ?? 1)) * 100
      : 0;

  healthChart.setOption({
    color: ["#1F4E79"],
    tooltip: {},
    radar: {
      radius: "68%",
      indicator: [
        { name: "完成率", max: 100 },
        { name: "完成课次", max: 100 },
        { name: "RPE强度", max: 100 },
        { name: "疼痛风险", max: 100 },
      ],
      splitArea: {
        areaStyle: { color: ["#F8FBFD", "#EAF3F8"] },
      },
      axisName: { color: "#305496" },
    },
    series: [
      {
        name: "训练反馈",
        type: "radar",
        data: [{ name: "训练反馈", value: [completion, doneRate, rpe, pain] }],
        areaStyle: { color: "rgba(31, 78, 121, 0.18)" },
      },
    ],
  });
}

function renderCharts() {
  renderDistanceChart();
  renderTypeChart();
  renderStatusChart();
  renderHealthChart();
}

async function loadDashboard() {
  summary.value = await getDashboard(cycleId.value);
  await nextTick();
  renderCharts();
}

async function loadCycles() {
  cycles.value = await listTrainingCycles();
}

function resizeCharts() {
  distanceChart?.resize();
  typeChart?.resize();
  statusChart?.resize();
  healthChart?.resize();
}

onMounted(async () => {
  await loadCycles();
  await loadDashboard();
  window.addEventListener("resize", resizeCharts);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeCharts);
  distanceChart?.dispose();
  typeChart?.dispose();
  statusChart?.dispose();
  healthChart?.dispose();
});
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dashboard-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 132px;
  padding: 24px;
  color: #ffffff;
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(31, 78, 121, 0.98), rgba(48, 84, 150, 0.88)),
    radial-gradient(circle at top right, rgba(255, 242, 204, 0.28), transparent 42%);
  box-shadow: 0 16px 40px rgba(31, 78, 121, 0.18);
}

.hero-kicker {
  margin-bottom: 8px;
  color: #fff2cc;
  font-size: 13px;
  font-weight: 700;
}

.dashboard-hero h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.dashboard-hero p {
  margin: 10px 0 0;
  color: #dbeafe;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
}

.metric-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(130px, 1fr));
  gap: 12px;
}

.metric-tile {
  min-height: 112px;
  padding: 16px;
  border: 1px solid rgba(184, 201, 214, 0.8);
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 10px 26px rgba(31, 78, 121, 0.08);
}

.metric-tile span {
  display: block;
  color: #667085;
  font-size: 13px;
}

.metric-tile strong {
  display: block;
  margin-top: 10px;
  color: #1f4e79;
  font-size: 28px;
  line-height: 1;
}

.metric-tile em {
  display: block;
  margin-top: 10px;
  color: #98a2b3;
  font-size: 12px;
  font-style: normal;
}

.metric-tile.highlight {
  background: #fffdf0;
  border-color: #f0d98a;
}

.metric-tile.pain strong {
  color: #c95f5f;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.chart-card,
.summary-table-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(184, 201, 214, 0.82);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 10px 26px rgba(31, 78, 121, 0.08);
}

.chart-card.wide {
  min-height: 360px;
}

.chart-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.chart-card-head h3 {
  margin: 0;
  color: #1f2933;
  font-size: 16px;
}

.chart-card-head p {
  margin: 5px 0 0;
  color: #667085;
  font-size: 13px;
}

.chart-badge {
  padding: 4px 9px;
  border-radius: 999px;
  color: #1f4e79;
  background: #ddebf7;
  font-size: 12px;
  font-weight: 700;
}

.chart {
  width: 100%;
  height: 300px;
}

.summary-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid #d5e2ec;
  border-radius: 10px;
  font-size: 13px;
}

.summary-table th {
  padding: 10px 9px;
  color: #ffffff;
  background: #1f4e79;
  text-align: center;
}

.summary-table td {
  padding: 10px 9px;
  border-top: 1px solid #d5e2ec;
  background: #f8fbfd;
  text-align: center;
}

.summary-table td:first-child {
  color: #1f4e79;
  background: #eaf3f8;
  font-weight: 700;
}

@media (max-width: 1200px) {
  .metric-strip {
    grid-template-columns: repeat(3, minmax(130px, 1fr));
  }
}

@media (max-width: 980px) {
  .dashboard-hero,
  .hero-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .metric-strip {
    grid-template-columns: 1fr;
  }
}
</style>
