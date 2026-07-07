<template>
  <div class="page-stack dashboard-page">
    <PageHeader title="训练统计" :subtitle="`${currentCycleName} · 训练计划、完成情况、强度结构和身体反馈的实时概览。`">
      <template v-if="!hasNoCycles && !hasNoActiveCycle" #actions>
        <div class="hero-actions">
          <el-select
            v-model="cycleId"
            filterable
            placeholder="当前训练周期"
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
          <el-button :icon="Refresh" type="primary" @click="reloadAll">刷新</el-button>
          <el-button @click="router.push('/weekly-review')">周复盘</el-button>
        </div>
      </template>
    </PageHeader>

    <section v-if="hasNoCycles" class="onboarding-card">
      <div class="onboarding-copy">
        <div class="onboarding-kicker">首次使用</div>
        <h3>欢迎使用 GaitLogic Planner</h3>
        <p>先选择一种方式建立你的第一份训练计划。导入现有课表更快，AI 教练适合从目标赛事开始生成草稿。</p>
      </div>
      <div class="onboarding-actions">
        <button class="start-option excel-option" type="button" @click="router.push('/plan-imports')">
          <span class="start-option-icon">IMP</span>
          <strong>导入课表</strong>
          <em>支持 Excel、CSV、TXT、Markdown 和 JSON，先生成草稿再确认应用。</em>
        </button>
        <button class="start-option ai-option" type="button" @click="router.push('/ai-plan')">
          <span class="start-option-icon">AI</span>
          <strong>用 AI 教练生成</strong>
          <em>输入当前能力、目标赛事和训练偏好，先生成可编辑草稿。</em>
        </button>
      </div>
    </section>

    <section v-else-if="hasNoActiveCycle" class="empty-data-card">
      <h3>当前没有正在进行的训练周期</h3>
      <p>系统首页、今日训练和训练计划默认只显示 active 周期的数据。请先到训练周期页面启用一个草稿周期。</p>
      <div>
        <el-button type="primary" @click="router.push('/cycles')">去启用周期</el-button>
      </div>
    </section>

    <section v-else-if="hasNoWorkoutData" class="empty-data-card">
      <h3>当前范围还没有训练计划</h3>
      <p>可以先导入外部课表，或到训练计划页面手动创建训练内容。</p>
      <div>
        <el-button type="primary" @click="router.push('/plan-imports')">去课表导入</el-button>
        <el-button @click="router.push('/workouts')">查看训练计划</el-button>
      </div>
    </section>

    <template v-else>
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

 <section class="summary-table-card">
        <div class="chart-card-head">
          <div>
            <h3>执行摘要</h3>
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


      <section class="chart-grid">
        <article class="chart-card wide">
          <div class="chart-card-head">
            <div>
              <h3>计划 vs 实际公里</h3>
              <p>{{ distanceModeHint }}</p>
            </div>
            <el-radio-group v-model="distanceMode" size="small" @change="renderDistanceChart">
              <el-radio-button label="cycle">当前周期</el-radio-button>
              <el-radio-button label="month">月跑量</el-radio-button>
              <el-radio-button label="week">周跑量</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="distanceChartRef" class="chart"></div>
        </article>

        <article class="chart-card wide">
          <div class="chart-card-head">
            <div>
              <h3>训练类型分布</h3>
              <p>{{ typeModeHint }}</p>
            </div>
            <el-radio-group v-model="typeMode" size="small" @change="renderTypeChart">
              <el-radio-button label="cycle">当前周期</el-radio-button>
              <el-radio-button label="month">月跑量</el-radio-button>
              <el-radio-button label="week">周跑量</el-radio-button>
            </el-radio-group>
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

        <article class="chart-card">
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Refresh } from "@element-plus/icons-vue";
import * as echarts from "echarts";

import { getDashboard } from "@/api/dashboard";
import { listPlannedWorkouts } from "@/api/plannedWorkouts";
import { listTrainingBlocks } from "@/api/trainingBlocks";
import { getActiveTrainingCycle, listTrainingCycles } from "@/api/trainingCycles";
import type { DashboardSummary, PlannedWorkout, TrainingBlock, TrainingCycle } from "@/types/models";
import { labelFor, mainTypeOptions } from "@/types/options";

type ChartMode = "cycle" | "month" | "week";

interface DistanceBucket {
  name: string;
  order: string | number;
  planned: number;
  actual: number;
}

interface TypeBucket {
  name: string;
  order: string | number;
  values: Map<string, number>;
}

const router = useRouter();
const cycleId = ref<number | null>(null);
const activeCycle = ref<TrainingCycle | null>(null);
const cycles = ref<TrainingCycle[]>([]);
const blocks = ref<TrainingBlock[]>([]);
const workouts = ref<PlannedWorkout[]>([]);
const summary = ref<DashboardSummary | null>(null);
const distanceMode = ref<ChartMode>("cycle");
const typeMode = ref<ChartMode>("cycle");

const distanceChartRef = ref<HTMLDivElement | null>(null);
const typeChartRef = ref<HTMLDivElement | null>(null);
const statusChartRef = ref<HTMLDivElement | null>(null);
const healthChartRef = ref<HTMLDivElement | null>(null);

let distanceChart: echarts.ECharts | null = null;
let typeChart: echarts.ECharts | null = null;
let statusChart: echarts.ECharts | null = null;
let healthChart: echarts.ECharts | null = null;

const palette = ["#1976d2", "#1f7a68", "#ff8a00", "#7b68aa", "#bc4b4b", "#5f8d4e", "#8293a4"];

const hasNoCycles = computed(() => cycles.value.length === 0);
const hasNoActiveCycle = computed(() => !hasNoCycles.value && !activeCycle.value);
const hasNoWorkoutData = computed(() => !hasNoCycles.value && !hasNoActiveCycle.value && !!summary.value && summary.value.workout_count === 0);

const currentCycleName = computed(() => {
  if (activeCycle.value && cycleId.value === activeCycle.value.id) return activeCycle.value.name;
  if (!cycleId.value) return "当前没有正在进行的训练周期";
  return cycles.value.find((cycle) => cycle.id === cycleId.value)?.name || "当前周期";
});

const distanceModeHint = computed(() => {
  if (distanceMode.value === "month") return "按月份统计计划公里和实际公里";
  if (distanceMode.value === "week") return "按训练块 / 周统计计划公里和实际公里";
  return "当前训练周期总量对比";
});

const typeModeHint = computed(() => {
  if (typeMode.value === "month") return "按月份查看各训练类型公里堆叠";
  if (typeMode.value === "week") return "按训练块 / 周查看各训练类型公里堆叠";
  return "悬停查看各训练类型公里数和次数";
});

const cycleNameMap = computed(() => new Map(cycles.value.map((cycle) => [cycle.id, cycle.name])));
const blockMap = computed(() => new Map(blocks.value.map((block) => [block.id, block])));

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
  return numeric(value).toFixed(1);
}

function workoutKm(workout: PlannedWorkout) {
  const actual = numeric(workout.workout_log?.actual_distance_km);
  return actual > 0 ? actual : numeric(workout.planned_distance_km);
}

function monthKey(dateText?: string | null) {
  if (!dateText) return "未填日期";
  return dateText.slice(0, 7);
}

function blockLabel(workout: PlannedWorkout) {
  const block = blockMap.value.get(workout.block_id);
  return block?.block_name || workout.phase_name || `训练块 ${workout.block_id}`;
}

function blockOrder(workout: PlannedWorkout) {
  return blockMap.value.get(workout.block_id)?.sort_order ?? workout.block_id;
}

function addToBucket(map: Map<string, DistanceBucket>, key: string, name: string, order: string | number, workout: PlannedWorkout) {
  const bucket = map.get(key) || { name, order, planned: 0, actual: 0 };
  bucket.planned += numeric(workout.planned_distance_km);
  bucket.actual += numeric(workout.workout_log?.actual_distance_km);
  map.set(key, bucket);
}

function buildDistanceBuckets() {
  const map = new Map<string, DistanceBucket>();
  for (const workout of workouts.value) {
    if (distanceMode.value === "month") {
      const key = monthKey(workout.workout_date);
      addToBucket(map, key, key, key, workout);
      continue;
    }
    if (distanceMode.value === "week") {
      const key = String(workout.block_id);
      addToBucket(map, key, blockLabel(workout), blockOrder(workout), workout);
      continue;
    }
    const key = String(workout.cycle_id);
    const name = cycleNameMap.value.get(workout.cycle_id) || currentCycleName.value;
    addToBucket(map, key, name, workout.cycle_id, workout);
  }

  return Array.from(map.values()).sort((a, b) =>
    String(a.order).localeCompare(String(b.order), "zh-Hans-CN", { numeric: true }),
  );
}

function buildTypeRows() {
  const map = new Map<string, { name: string; count: number; km: number }>();
  for (const workout of workouts.value) {
    const key = workout.main_type_normalized;
    const current = map.get(key) || {
      name: labelFor(mainTypeOptions, key as never),
      count: 0,
      km: 0,
    };
    current.count += 1;
    current.km += workoutKm(workout);
    map.set(key, current);
  }
  return Array.from(map.values()).sort((a, b) => b.km - a.km);
}

function addTypeBucket(map: Map<string, TypeBucket>, key: string, name: string, order: string | number, workout: PlannedWorkout) {
  const typeName = labelFor(mainTypeOptions, workout.main_type_normalized as never);
  const bucket = map.get(key) || { name, order, values: new Map<string, number>() };
  bucket.values.set(typeName, (bucket.values.get(typeName) || 0) + workoutKm(workout));
  map.set(key, bucket);
}

function buildTypeBuckets() {
  const map = new Map<string, TypeBucket>();
  for (const workout of workouts.value) {
    if (typeMode.value === "month") {
      const key = monthKey(workout.workout_date);
      addTypeBucket(map, key, key, key, workout);
      continue;
    }
    if (typeMode.value === "week") {
      const key = String(workout.block_id);
      addTypeBucket(map, key, blockLabel(workout), blockOrder(workout), workout);
      continue;
    }
    const key = String(workout.cycle_id);
    const name = cycleNameMap.value.get(workout.cycle_id) || currentCycleName.value;
    addTypeBucket(map, key, name, workout.cycle_id, workout);
  }
  return Array.from(map.values()).sort((a, b) =>
    String(a.order).localeCompare(String(b.order), "zh-Hans-CN", { numeric: true }),
  );
}

function renderDistanceChart() {
  if (!distanceChartRef.value || !summary.value || hasNoWorkoutData.value) return;
  distanceChart ||= echarts.init(distanceChartRef.value);
  const buckets = buildDistanceBuckets();
  distanceChart.setOption({
    color: ["#1976d2", "#1f7a68"],
    tooltip: { trigger: "axis", valueFormatter: (value: number) => `${fmt(value)} km` },
    legend: { top: 0, data: ["计划公里", "实际公里"] },
    grid: { left: 48, right: 24, top: 48, bottom: 42 },
    xAxis: {
      type: "category",
      data: buckets.map((item) => item.name),
      axisTick: { show: false },
      axisLabel: { interval: 0, rotate: buckets.length > 6 ? 28 : 0 },
    },
    yAxis: { type: "value", name: "km", splitLine: { lineStyle: { color: "#e5e5e5" } } },
    series: [
      {
        name: "计划公里",
        type: "bar",
        barMaxWidth: 34,
        data: buckets.map((item) => Number(item.planned.toFixed(1))),
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
      {
        name: "实际公里",
        type: "bar",
        barMaxWidth: 34,
        data: buckets.map((item) => Number(item.actual.toFixed(1))),
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
    ],
  });
}

function renderTypeChart() {
  if (!typeChartRef.value || !summary.value || hasNoWorkoutData.value) return;
  typeChart ||= echarts.init(typeChartRef.value);

  if (typeMode.value === "cycle") {
    const data = buildTypeRows().map((row) => ({
      name: row.name,
      value: Number(row.km.toFixed(1)),
      count: row.count,
    }));
    typeChart.setOption(
      {
        color: palette,
        tooltip: {
          trigger: "item",
          formatter: (params: any) =>
            `${params.name}<br/>公里：${fmt(params.value)} km<br/>次数：${params.data.count}`,
        },
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
      },
      true,
    );
    return;
  }

  const buckets = buildTypeBuckets();
  const typeNames = Array.from(new Set(buckets.flatMap((bucket) => Array.from(bucket.values.keys()))));
  typeChart.setOption(
    {
      color: palette,
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (value: number) => `${fmt(value)} km` },
      legend: { top: 0, type: "scroll", data: typeNames },
      grid: { left: 48, right: 24, top: 54, bottom: 42 },
      xAxis: {
        type: "category",
        data: buckets.map((bucket) => bucket.name),
        axisTick: { show: false },
        axisLabel: { interval: 0, rotate: buckets.length > 6 ? 28 : 0 },
      },
      yAxis: { type: "value", name: "km", splitLine: { lineStyle: { color: "#e5e5e5" } } },
      series: typeNames.map((name) => ({
        name,
        type: "bar",
        stack: "type-km",
        barMaxWidth: 38,
        emphasis: { focus: "series" },
        data: buckets.map((bucket) => Number((bucket.values.get(name) || 0).toFixed(1))),
      })),
    },
    true,
  );
}

function renderStatusChart() {
  if (!statusChartRef.value || !summary.value || hasNoWorkoutData.value) return;
  statusChart ||= echarts.init(statusChartRef.value);
  statusChart.setOption({
    color: ["#1f7a68", "#bc4b4b", "#1976d2"],
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
  if (!healthChartRef.value || !summary.value || hasNoWorkoutData.value) return;
  healthChart ||= echarts.init(healthChartRef.value);
  const completion = Math.min(numeric(summary.value.completion_rate), 100);
  const rpe = Math.min(numeric(summary.value.avg_rpe) * 10, 100);
  const pain = Math.min(numeric(summary.value.max_pain_level) * 10, 100);
  const doneRate =
    (summary.value.workout_count ?? 0) > 0
      ? ((summary.value.completed_count ?? 0) / (summary.value.workout_count ?? 1)) * 100
      : 0;

  healthChart.setOption({
    color: ["#1976d2"],
    tooltip: {},
    radar: {
      radius: "68%",
      indicator: [
        { name: "完成率", max: 100 },
        { name: "完成课次", max: 100 },
        { name: "RPE强度", max: 100 },
        { name: "疼痛风险", max: 100 },
      ],
      splitArea: { areaStyle: { color: ["#ffffff", "#f3f8fc"] } },
      axisName: { color: "#384353" },
    },
    series: [
      {
        name: "训练反馈",
        type: "radar",
        data: [{ name: "训练反馈", value: [completion, doneRate, rpe, pain] }],
        areaStyle: { color: "rgba(25, 118, 210, 0.16)" },
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

function disposeCharts() {
  distanceChart?.dispose();
  typeChart?.dispose();
  statusChart?.dispose();
  healthChart?.dispose();
  distanceChart = null;
  typeChart = null;
  statusChart = null;
  healthChart = null;
}

async function loadDashboard() {
  if (hasNoCycles.value || hasNoActiveCycle.value) {
    summary.value = null;
    workouts.value = [];
    blocks.value = [];
    disposeCharts();
    return;
  }

  summary.value = await getDashboard(cycleId.value);
  workouts.value = await listPlannedWorkouts({ cycle_id: cycleId.value });
  blocks.value = await listTrainingBlocks(cycleId.value);

  if (hasNoWorkoutData.value) {
    disposeCharts();
    return;
  }
  await nextTick();
  renderCharts();
}

async function loadCycles() {
  cycles.value = await listTrainingCycles();
  try {
    activeCycle.value = await getActiveTrainingCycle();
    cycleId.value = activeCycle.value.id;
  } catch {
    activeCycle.value = null;
    cycleId.value = null;
  }
}

async function reloadAll() {
  await loadCycles();
  await loadDashboard();
}

function resizeCharts() {
  distanceChart?.resize();
  typeChart?.resize();
  statusChart?.resize();
  healthChart?.resize();
}

onMounted(async () => {
  await reloadAll();
  window.addEventListener("resize", resizeCharts);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeCharts);
  disposeCharts();
});
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1300px;
  min-height: calc(100vh - 98px);
  margin: 0 auto;
  padding: 24px 50px 42px;
  background: #ffffff;
}

.dashboard-hero,
.onboarding-card,
.empty-data-card {
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.dashboard-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 118px;
  padding: 22px;
  color: #182230;
}

.hero-kicker,
.onboarding-kicker {
  margin-bottom: 8px;
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.dashboard-hero h2,
.onboarding-card h3,
.empty-data-card h3 {
  margin: 0;
  color: #172033;
  font-size: 28px;
  line-height: 1.2;
}

.dashboard-hero p,
.onboarding-card p,
.empty-data-card p {
  margin: 10px 0 0;
  color: #667085;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: #f8fafc;
}

.onboarding-card {
  display: grid;
  grid-template-columns: minmax(260px, 0.78fr) minmax(360px, 1fr);
  gap: 26px;
  align-items: stretch;
  padding: 30px;
  background:
    radial-gradient(circle at 18% 10%, rgba(25, 118, 210, 0.08), transparent 28%),
    #ffffff;
}

.onboarding-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.onboarding-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.start-option {
  min-height: 168px;
  padding: 18px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #fbfdff;
  color: #172033;
  text-align: left;
  cursor: pointer;
  box-shadow: var(--card-shadow);
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease;
}

.start-option:hover {
  transform: translateY(-2px);
  border-color: #1976d2;
  background: #ffffff;
  box-shadow: 0 14px 34px rgba(25, 118, 210, 0.14);
}

.start-option-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  margin-bottom: 18px;
  border-radius: 8px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.excel-option .start-option-icon {
  background: #13a366;
}

.ai-option .start-option-icon {
  background: #1976d2;
}

.start-option strong {
  display: block;
  color: #172033;
  font-size: 18px;
  line-height: 1.25;
}

.start-option em {
  display: block;
  margin-top: 10px;
  color: #667085;
  font-size: 13px;
  font-style: normal;
  line-height: 1.7;
}

.empty-data-card {
  padding: 30px;
  text-align: center;
}

.empty-data-card div {
  margin-top: 18px;
}

.metric-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(130px, 1fr));
  gap: 12px;
}

.metric-tile {
  min-height: 112px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--shadow-sm);
}

.metric-tile span {
  display: block;
  color: #667085;
  font-size: 13px;
}

.metric-tile strong {
  display: block;
  margin-top: 10px;
  color: #1976d2;
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
  border-color: #cfe2f3;
  background: #f7fbff;
}

.metric-tile.pain strong {
  color: #bc4b4b;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.chart-card,
.summary-table-card {
  min-width: 0;
  overflow-x: auto;
  padding: 16px;
  border: 1px solid #d7d7d7;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.2);
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
  color: #384353;
  font-size: 16px;
  font-weight: 500;
}

.chart-card-head p {
  margin: 5px 0 0;
  color: #667085;
  font-size: 13px;
}

.chart-badge {
  padding: 4px 9px;
  border-radius: 999px;
  color: #1976d2;
  background: #e7f1f8;
  font-size: 12px;
  font-weight: 700;
}

.chart {
  width: 100%;
  height: 300px;
}

.summary-table {
  width: 100%;
  min-width: 720px;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  font-size: 13px;
}

.summary-table th {
  padding: 10px 9px;
  color: #344054;
  background: #f8fafc;
  text-align: center;
}

.summary-table td {
  padding: 10px 9px;
  border-top: 1px solid var(--line-soft);
  background: #ffffff;
  text-align: center;
}

.summary-table td:first-child {
  color: #1976d2;
  background: #f7fbff;
  font-weight: 700;
}

@media (max-width: 1200px) {
  .metric-strip {
    grid-template-columns: repeat(3, minmax(130px, 1fr));
  }
}

@media (max-width: 980px) {
  .dashboard-hero,
  .hero-actions,
  .onboarding-card {
    align-items: stretch;
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .onboarding-actions {
    grid-template-columns: 1fr;
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .dashboard-page {
    padding: 16px 10px 84px;
  }

  .metric-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .metric-tile {
    min-height: 76px;
    padding: 10px 12px;
  }

  .metric-tile span {
    font-size: 12px;
  }

  .metric-tile strong {
    margin-top: 6px;
    font-size: 22px;
  }

  .metric-tile em {
    display: none;
  }

  .summary-table-card {
    padding: 10px;
  }

  .summary-table {
    min-width: 660px;
    font-size: 12px;
  }
}
</style>
