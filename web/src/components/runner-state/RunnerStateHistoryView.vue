<template>
  <div class="history-view">
    <section class="range-toolbar" aria-label="历史时间范围">
      <div class="range-copy"><strong>查看范围</strong><span v-if="timeline">{{ formatDate(timeline.start_date) }} 至 {{ formatDate(timeline.end_date) }}</span></div>
      <el-radio-group v-model="selectedRange" :disabled="timelineLoading" @change="changeRange">
        <el-radio-button value="28d">近28天</el-radio-button>
        <el-radio-button value="12w">近12周</el-radio-button>
        <el-radio-button value="6m">近6个月</el-radio-button>
      </el-radio-group>
    </section>

    <el-alert v-if="timelineError" type="warning" :closable="false" show-icon title="趋势加载失败，仍保留上一次成功结果。" :description="timelineError" />
    <div v-if="timelineLoading && !timeline" class="history-loading"><el-skeleton :rows="10" animated /></div>
    <template v-else-if="timeline">
      <div v-if="!timeline.items.length" class="history-empty">
        <el-empty description="还没有训练状态记录">
          <p>保存一次当前状态后，这里会开始形成你的训练状态时间线。</p>
          <el-button type="primary" @click="$emit('return-current')">返回当前状态</el-button>
        </el-empty>
      </div>
      <template v-else>
        <RunnerStateHistorySummary :timeline="timeline" />
        <RunnerStateVolumeChart :items="timeline.items" />
        <RunnerStateTimeline :items="timeline.items" />
        <RunnerStateRiskTimeline :items="timeline.items" @open-detail="openDetail" />
        <RunnerStateDataQualityTrend :items="timeline.items" />
      </template>
      <RunnerStateSnapshotList
        :response="snapshotList"
        :current-page="currentPage"
        :loading="listLoading"
        :error="listError"
        @page-change="changePage"
        @open-detail="openDetail"
      />
    </template>
    <RunnerStateSnapshotDetail
      :visible="detailVisible"
      :detail="detail"
      :loading="detailLoading"
      :error="detailError"
      @update:visible="updateDetailVisibility"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import {
  getRunnerStateSnapshotDetail,
  getRunnerStateTimeline,
  listRunnerStateSnapshots,
} from "@/api/runnerState";
import { getRequestErrorMessage } from "@/api/request";
import RunnerStateDataQualityTrend from "./RunnerStateDataQualityTrend.vue";
import RunnerStateHistorySummary from "./RunnerStateHistorySummary.vue";
import RunnerStateRiskTimeline from "./RunnerStateRiskTimeline.vue";
import RunnerStateSnapshotDetail from "./RunnerStateSnapshotDetail.vue";
import RunnerStateSnapshotList from "./RunnerStateSnapshotList.vue";
import RunnerStateTimeline from "./RunnerStateTimeline.vue";
import RunnerStateVolumeChart from "./RunnerStateVolumeChart.vue";
import type {
  RunnerStateSnapshotDetail as SnapshotDetail,
  RunnerStateSnapshotListResponse,
  RunnerStateTimelineRange,
  RunnerStateTimelineResponse,
} from "@/types/runnerState";
import { formatDate } from "@/utils/runnerStateFormat";

defineEmits<{ "return-current": [] }>();
const selectedRange = ref<RunnerStateTimelineRange>("28d");
const timeline = ref<RunnerStateTimelineResponse | null>(null);
const snapshotList = ref<RunnerStateSnapshotListResponse | null>(null);
const timelineLoading = ref(false);
const listLoading = ref(false);
const detailLoading = ref(false);
const timelineError = ref("");
const listError = ref("");
const detailError = ref("");
const currentPage = ref(1);
const detailVisible = ref(false);
const detail = ref<SnapshotDetail | null>(null);
const pageSize = 30;
let timelineRequestId = 0;
let listRequestId = 0;
let timelineController: AbortController | null = null;
let listController: AbortController | null = null;
let detailController: AbortController | null = null;
let detailRequestId = 0;

async function loadList(startDate: string, endDate: string, page = currentPage.value) {
  const requestId = ++listRequestId;
  listController?.abort();
  listController = new AbortController();
  listLoading.value = true;
  listError.value = "";
  try {
    const response = await listRunnerStateSnapshots({
      start_date: startDate,
      end_date: endDate,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }, listController.signal);
    if (requestId !== listRequestId) return;
    snapshotList.value = response;
    currentPage.value = page;
  } catch (error) {
    if (requestId !== listRequestId || listController.signal.aborted) return;
    listError.value = getRequestErrorMessage(error);
  } finally {
    if (requestId === listRequestId) listLoading.value = false;
  }
}

async function loadHistory(range = selectedRange.value) {
  const requestId = ++timelineRequestId;
  timelineController?.abort();
  timelineController = new AbortController();
  timelineLoading.value = true;
  timelineError.value = "";
  try {
    const response = await getRunnerStateTimeline(range, timelineController.signal);
    if (requestId !== timelineRequestId) return;
    timeline.value = response;
    selectedRange.value = response.range;
    currentPage.value = 1;
    await loadList(response.start_date, response.end_date, 1);
  } catch (error) {
    if (requestId !== timelineRequestId || timelineController.signal.aborted) return;
    timelineError.value = getRequestErrorMessage(error);
  } finally {
    if (requestId === timelineRequestId) timelineLoading.value = false;
  }
}

function changeRange(value: string | number | boolean | undefined) {
  if (value === "28d" || value === "12w" || value === "6m") loadHistory(value);
}
function changePage(page: number) {
  if (timeline.value) loadList(timeline.value.start_date, timeline.value.end_date, page);
}
async function openDetail(snapshotId: number) {
  const requestId = ++detailRequestId;
  detailController?.abort();
  const controller = new AbortController();
  detailController = controller;
  detailVisible.value = true;
  detailLoading.value = true;
  detailError.value = "";
  detail.value = null;
  try {
    const response = await getRunnerStateSnapshotDetail(snapshotId, controller.signal);
    if (requestId === detailRequestId) detail.value = response;
  } catch (error) {
    if (requestId === detailRequestId && !controller.signal.aborted) detailError.value = getRequestErrorMessage(error);
  } finally {
    if (requestId === detailRequestId && !controller.signal.aborted) detailLoading.value = false;
  }
}

function updateDetailVisibility(visible: boolean) {
  detailVisible.value = visible;
  if (visible) return;
  detailRequestId += 1;
  detailController?.abort();
  detailController = null;
  detailLoading.value = false;
  detailError.value = "";
  detail.value = null;
}

defineExpose({ refresh: () => loadHistory(selectedRange.value) });
onMounted(() => loadHistory());
onBeforeUnmount(() => { timelineController?.abort(); listController?.abort(); detailController?.abort(); });
</script>

<style scoped>
.history-view { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.range-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px 16px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; }
.range-copy { display: flex; flex-direction: column; gap: 3px; }.range-toolbar span { color: var(--muted); font-size: 12px; }.history-loading { padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; }.history-empty { padding: 16px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; }.history-empty p { color: var(--muted); }
@media (max-width: 768px) { .range-toolbar { align-items: stretch; flex-direction: column; } .range-toolbar :deep(.el-radio-group) { display: grid; grid-template-columns: repeat(3, 1fr); } .range-toolbar :deep(.el-radio-button__inner) { width: 100%; min-height: 44px; padding: 12px 6px; } }
@media (max-width: 340px) { .range-toolbar :deep(.el-radio-group) { grid-template-columns: 1fr; } }
</style>
