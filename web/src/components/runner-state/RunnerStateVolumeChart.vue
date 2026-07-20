<template>
  <section class="history-card" aria-labelledby="volume-chart-title">
    <header><div><h2 id="volume-chart-title">跑量趋势</h2><p>缺失值保持为空，不补成 0。</p></div><span>km</span></header>
    <div v-if="items.length" ref="chartRef" class="volume-chart" role="img" aria-label="最近7天与最近28天周均跑量趋势图" />
    <el-empty v-else :image-size="60" description="当前范围没有跑量记录" />
    <div v-if="items.length" class="accessible-table-wrap">
      <table>
        <caption>跑量趋势数据表</caption>
        <thead><tr><th>截止日期</th><th>最近7天</th><th>28天周均</th></tr></thead>
        <tbody><tr v-for="item in items" :key="item.id"><td>{{ formatDate(item.data_cutoff_date) }}</td><td>{{ formatDistance(item.distance_7d_km) }}</td><td>{{ formatDistance(item.distance_28d_weekly_average_km) }}</td></tr></tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import * as echarts from "echarts";
import type { ECharts } from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { RunnerStateTimelineItem } from "@/types/runnerState";
import { formatDate, formatDistance } from "@/utils/runnerStateFormat";

const props = defineProps<{ items: RunnerStateTimelineItem[] }>();
const chartRef = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;

async function renderChart() {
  await nextTick();
  if (!chartRef.value || !props.items.length) return;
  chart ||= echarts.init(chartRef.value);
  chart.setOption({
    color: ["#1976d2", "#1f7a68"],
    tooltip: { trigger: "axis", valueFormatter: (value: number | null) => value === null ? "暂无数据" : `${value} km` },
    legend: { top: 0, data: ["最近7天", "28天周均"] },
    grid: { left: 48, right: 22, top: 46, bottom: 48 },
    xAxis: { type: "category", data: props.items.map((item) => item.data_cutoff_date.slice(5)), axisLabel: { interval: props.items.length > 12 ? "auto" : 0 } },
    yAxis: { type: "value", name: "km", min: 0, splitLine: { lineStyle: { color: "#e8edf2" } } },
    series: [
      { name: "最近7天", type: "line", connectNulls: false, symbolSize: 7, data: props.items.map((item) => item.distance_7d_km ?? null) },
      { name: "28天周均", type: "line", connectNulls: false, symbolSize: 7, data: props.items.map((item) => item.distance_28d_weekly_average_km ?? null) },
    ],
  }, true);
}

function resize() { chart?.resize(); }
watch(() => props.items, renderChart, { deep: true });
onMounted(() => { renderChart(); window.addEventListener("resize", resize); });
onBeforeUnmount(() => { window.removeEventListener("resize", resize); chart?.dispose(); chart = null; });
</script>

<style scoped>
.history-card { min-width: 0; padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
header { display: flex; justify-content: space-between; gap: 16px; }
h2 { margin: 0; color: #172033; font-size: 18px; } header p { margin: 5px 0 0; color: var(--muted); font-size: 12px; } header span { color: var(--muted); }
.volume-chart { width: 100%; height: 300px; margin-top: 12px; }
.accessible-table-wrap { overflow-x: auto; margin-top: 10px; }
table { width: 100%; min-width: 460px; border-collapse: collapse; font-size: 12px; }
caption { padding: 8px; color: var(--muted); text-align: left; }
th, td { padding: 8px; border-top: 1px solid var(--line-soft); text-align: left; }
@media (max-width: 680px) { .history-card { padding: 14px; } .volume-chart { height: 250px; min-width: 520px; } .history-card { overflow-x: auto; } }
</style>
