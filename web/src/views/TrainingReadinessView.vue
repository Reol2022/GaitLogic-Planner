<template>
  <div class="page-stack readiness-page">
    <PageHeader
      title="负荷与恢复"
      subtitle="查看训练负荷、恢复趋势、疼痛记录和当前训练状态参考。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="reload">刷新</el-button>
        <el-button type="primary" :icon="EditPen" @click="checkinDialogVisible = true">填写恢复状态</el-button>
      </template>
    </PageHeader>

    <el-alert
      v-if="availabilityMessage"
      :title="availabilityMessage"
      :type="availabilityType"
      show-icon
      :closable="false"
    />

    <template v-if="todayReadiness">
      <section class="panel status-panel">
        <div class="panel-header">
          <h2 class="panel-title">当前状态</h2>
          <el-tag :class="readinessStatusClass(todayReadiness.assessment.status)" effect="plain">
            {{ readinessStatusLabel(todayReadiness.assessment.status) }}
          </el-tag>
        </div>
        <div class="panel-body status-body">
          <div class="status-copy">
            <strong>{{ readinessStatusLabel(todayReadiness.assessment.status) }}</strong>
            <span>数据质量：{{ dataQualityLabel(todayReadiness.assessment.data_quality) }}</span>
            <span>最近计算：{{ formatDateTime(todayReadiness.assessment.generated_at) }}</span>
            <span>今日恢复打卡：{{ todayReadiness.recovery_checkin_completed ? "已完成" : "未完成" }}</span>
          </div>
          <div class="status-list">
            <h3>主要原因</h3>
            <ul>
              <li v-for="reason in todayReadiness.assessment.reasons_json" :key="reason">{{ reason }}</li>
            </ul>
          </div>
          <div class="status-list">
            <h3>今日建议</h3>
            <ul>
              <li v-for="item in todayReadiness.assessment.recommendations_json" :key="item.action">
                {{ item.message }}
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section class="metric-grid readiness-metrics">
        <div class="metric-card">
          <p class="metric-label">最近 7 天 sRPE</p>
          <div class="metric-value">{{ fmt(summary?.rolling_7d_srpe_load_au) }}</div>
        </div>
        <div class="metric-card">
          <p class="metric-label">28 天平均周 sRPE</p>
          <div class="metric-value">{{ fmt(summary?.baseline_28d_weekly_srpe_load_au) }}</div>
        </div>
        <div class="metric-card">
          <p class="metric-label">最近 7 天跑量</p>
          <div class="metric-value">{{ fmt(summary?.rolling_7d_distance_km) }} km</div>
        </div>
        <div class="metric-card">
          <p class="metric-label">28 天平均周跑量</p>
          <div class="metric-value">{{ fmt(summary?.baseline_28d_weekly_distance_km) }} km</div>
        </div>
        <div class="metric-card">
          <p class="metric-label">恢复打卡覆盖率</p>
          <div class="metric-value">{{ percent(summary?.recovery_checkin_coverage_ratio) }}</div>
        </div>
        <div class="metric-card">
          <p class="metric-label">时长与 RPE 覆盖率</p>
          <div class="metric-value">{{ percent(summary?.srpe_coverage_ratio) }}</div>
        </div>
      </section>

      <section class="readiness-grid">
        <article class="panel">
          <div class="panel-header">
            <h2 class="panel-title">训练负荷</h2>
          </div>
          <div class="panel-body info-list">
            <span>最近 7 天训练时长：{{ fmt(summary?.rolling_7d_duration_minutes) }} 分钟</span>
            <span>高强度距离：{{ fmt(summary?.rolling_7d_high_intensity_distance_km) }} km</span>
            <span>关键课数量：{{ summary?.rolling_7d_key_workout_count ?? 0 }}</span>
            <span>完成训练次数：{{ summary?.rolling_7d_training_session_count ?? 0 }}</span>
            <span>负荷变化：{{ signedPercent(summary?.load_change_percentage) }}</span>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2 class="panel-title">恢复趋势</h2>
          </div>
          <div class="panel-body signal-list">
            <span v-for="signal in recoverySignals" :key="signal.signal_key">{{ signal.message }}</span>
            <el-empty v-if="recoverySignals.length === 0" description="暂无恢复异常信号" />
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2 class="panel-title">表现变化</h2>
          </div>
          <div class="panel-body signal-list">
            <span v-for="signal in performanceSignals" :key="signal.signal_key">{{ signal.message }}</span>
            <el-empty v-if="performanceSignals.length === 0" description="暂无明显表现异常" />
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2 class="panel-title">疼痛记录</h2>
          </div>
          <div class="panel-body signal-list">
            <span v-for="signal in painSignals" :key="signal.signal_key">{{ signal.message }}</span>
            <p class="medical-note">
              疼痛等级只用于训练状态参考，不构成医学分级或诊断。疼痛持续或加重时，请暂停高强度训练，并寻求具备资质的医疗或康复专业人员评估。
            </p>
          </div>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">趋势图</h2>
          <el-radio-group v-model="trendDays" size="small" @change="loadTrend">
            <el-radio-button :label="7">7 天</el-radio-button>
            <el-radio-button :label="28">28 天</el-radio-button>
            <el-radio-button :label="42">42 天</el-radio-button>
          </el-radio-group>
        </div>
        <div class="panel-body">
          <div ref="loadChartRef" class="chart"></div>
          <p class="chart-note">sRPE = 实际训练时长（分钟）× 整堂训练 RPE。缺少时长或 RPE 时不参与该日 sRPE 计算。</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">数据完整度</h2>
        </div>
        <div class="panel-body info-list">
          <span>最近 7 天恢复打卡：{{ Math.round((summary?.recovery_checkin_coverage_ratio ?? 0) * 7) }} / 7 天</span>
          <span>训练历史天数：{{ summary?.history_days ?? 0 }} 天</span>
          <span>缺失指标：{{ missingDataText }}</span>
          <span>历史不足或覆盖率偏低时，系统会降低数据质量等级，并避免给出激进调整。</span>
        </div>
      </section>
    </template>

    <el-dialog v-model="checkinDialogVisible" title="30 秒恢复打卡" width="620px">
      <el-alert
        title="这些数据仅用于生成个人训练负荷和恢复参考。你可以选择不填写任何高级身体指标。"
        type="info"
        :closable="false"
        class="privacy-alert"
      />
      <el-form label-position="top" class="checkin-form">
        <div class="form-grid">
          <el-form-item label="睡眠质量">
            <el-rate v-model="checkinForm.sleep_quality" :max="5" clearable />
          </el-form-item>
          <el-form-item label="主观疲劳">
            <el-slider v-model="checkinForm.subjective_fatigue" :min="1" :max="5" show-stops />
          </el-form-item>
          <el-form-item label="肌肉酸痛">
            <el-slider v-model="checkinForm.muscle_soreness" :min="1" :max="5" show-stops />
          </el-form-item>
          <el-form-item label="压力">
            <el-slider v-model="checkinForm.stress_level" :min="1" :max="5" show-stops />
          </el-form-item>
          <el-form-item label="腿感">
            <el-rate v-model="checkinForm.leg_feeling" :max="5" clearable />
          </el-form-item>
          <el-form-item label="疼痛等级">
            <el-slider v-model="checkinForm.pain_level" :min="0" :max="10" show-stops />
          </el-form-item>
        </div>
        <el-collapse>
          <el-collapse-item title="高级字段" name="advanced">
            <div class="form-grid">
              <el-form-item label="睡眠时长（分钟）">
                <el-input-number v-model="checkinForm.sleep_duration_minutes" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="心情">
                <el-rate v-model="checkinForm.mood_level" :max="5" clearable />
              </el-form-item>
              <el-form-item label="静息心率">
                <el-input-number v-model="checkinForm.resting_heart_rate_bpm" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="HRV">
                <el-input-number v-model="checkinForm.hrv_value" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="HRV 类型">
                <el-input v-model="checkinForm.hrv_metric" placeholder="如 rMSSD" />
              </el-form-item>
              <el-form-item label="HRV 来源">
                <el-input v-model="checkinForm.hrv_source" placeholder="如手动记录" />
              </el-form-item>
              <el-form-item label="疼痛部位">
                <el-input v-model="checkinForm.pain_location" />
              </el-form-item>
              <el-form-item label="疼痛趋势">
                <el-select v-model="checkinForm.pain_trend" style="width: 100%">
                  <el-option label="未知" value="unknown" />
                  <el-option label="好转" value="improving" />
                  <el-option label="稳定" value="stable" />
                  <el-option label="加重" value="worsening" />
                </el-select>
              </el-form-item>
              <el-form-item label="是否影响步态">
                <el-switch v-model="checkinForm.pain_affects_gait" />
              </el-form-item>
              <el-form-item label="疾病或异常症状">
                <el-input v-model="checkinForm.illness_symptoms" />
              </el-form-item>
              <el-form-item label="备注" class="full">
                <el-input v-model="checkinForm.notes" type="textarea" :rows="2" />
              </el-form-item>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="checkinDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingCheckin" @click="saveCheckin">保存并刷新状态</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { EditPen, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import * as echarts from "echarts";
import type { ECharts } from "echarts";

import {
  getTodayReadiness,
  getTrainingLoadTrend,
  recalculateReadiness,
  saveTodayRecoveryCheckin,
} from "@/api/trainingReadiness";
import { trackUsageEvent } from "@/api/usageEvents";
import type {
  DailyTrainingLoad,
  ReadinessDataQuality,
  RecoveryCheckinPayload,
  TrainingLoadSummaryRead,
  TrainingReadinessToday,
  TrainingStatus,
} from "@/types/models";

type Signal = { dimension: string; signal_key: string; level: string; message: string; evidence?: Record<string, unknown> };

const loading = ref(false);
const savingCheckin = ref(false);
const todayReadiness = ref<TrainingReadinessToday | null>(null);
const availabilityMessage = ref("");
const availabilityType = ref<"info" | "warning" | "error">("info");
const trendDays = ref(42);
const trendItems = ref<DailyTrainingLoad[]>([]);
const loadChartRef = ref<HTMLDivElement | null>(null);
const checkinDialogVisible = ref(false);
const checkinForm = reactive<RecoveryCheckinPayload>(initialCheckinForm());
let loadChart: ECharts | null = null;

const summary = computed(() => todayReadiness.value?.assessment.metrics_json as TrainingLoadSummaryRead | undefined);
const recoverySignals = computed(() => signalList(todayReadiness.value?.assessment.recovery_signals_json));
const performanceSignals = computed(() => signalList(todayReadiness.value?.assessment.performance_signals_json));
const painSignals = computed(() => signalList(todayReadiness.value?.assessment.pain_signals_json));
const missingDataText = computed(() => {
  const missing = summary.value?.missing_data || todayReadiness.value?.assessment.missing_data_json || [];
  if (!missing.length) return "暂无";
  return missing.map((item) => missingDataLabel(String(item))).join("、");
});

function initialCheckinForm(): RecoveryCheckinPayload {
  return {
    sleep_quality: null,
    subjective_fatigue: null,
    muscle_soreness: null,
    stress_level: null,
    leg_feeling: null,
    pain_level: 0,
    pain_trend: "unknown",
    pain_affects_gait: false,
  };
}

function signalList(value?: Array<Record<string, unknown>> | null): Signal[] {
  return (value || []).map((item) => ({
    dimension: String(item.dimension || ""),
    signal_key: String(item.signal_key || ""),
    level: String(item.level || ""),
    message: String(item.message || ""),
    evidence: (item.evidence || {}) as Record<string, unknown>,
  }));
}

function fmt(value?: number | string | null) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(1) : "-";
}

function percent(value?: number | null) {
  if (value == null) return "-";
  return `${Math.round(value * 100)}%`;
}

function signedPercent(value?: number | null) {
  if (value == null) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function readinessStatusLabel(value: TrainingStatus) {
  return {
    insufficient_data: "数据不足",
    normal: "状态稳定",
    watch: "关注恢复",
    reduce_load: "建议降负荷",
  }[value];
}

function readinessStatusClass(value: TrainingStatus) {
  return `readiness-tag readiness-${value}`;
}

function dataQualityLabel(value: ReadinessDataQuality) {
  return { low: "低", medium: "中", high: "高" }[value];
}

function missingDataLabel(value: string) {
  return {
    training_logs: "训练日志",
    duration_or_rpe: "实际时长或 RPE",
    recovery_checkins: "恢复打卡",
  }[value] || value;
}

function handleAvailability(error: unknown) {
  const status = (error as any)?.response?.status;
  if (status === 404) {
    availabilityMessage.value = "负荷与恢复功能暂未开放。";
    availabilityType.value = "info";
  } else if (status === 403) {
    availabilityMessage.value = "负荷与恢复功能当前处于灰度测试阶段。";
    availabilityType.value = "warning";
  } else if (status === 503) {
    availabilityMessage.value = "服务暂时不可用，请稍后重试。";
    availabilityType.value = "error";
  } else {
    availabilityMessage.value = "训练状态加载失败，请稍后重试。";
    availabilityType.value = "error";
  }
  todayReadiness.value = null;
}

async function loadToday() {
  try {
    todayReadiness.value = await getTodayReadiness();
    availabilityMessage.value = "";
    if (todayReadiness.value.assessment.status === "reduce_load") {
      trackUsageEvent("reduce_load_suggestion_viewed", {
        status: todayReadiness.value.assessment.status,
        data_quality: todayReadiness.value.assessment.data_quality,
      });
    }
    await nextTick();
    renderLoadChart();
  } catch (error) {
    handleAvailability(error);
  }
}

function dateDaysAgo(days: number) {
  const target = new Date();
  target.setDate(target.getDate() - days + 1);
  return target.toISOString().slice(0, 10);
}

async function loadTrend() {
  if (!todayReadiness.value) return;
  const startDate = dateDaysAgo(trendDays.value);
  const endDate = new Date().toISOString().slice(0, 10);
  trendItems.value = (await getTrainingLoadTrend(startDate, endDate)).items;
  await nextTick();
  renderLoadChart();
}

function renderLoadChart() {
  if (!loadChartRef.value || trendItems.value.length === 0) return;
  loadChart ||= echarts.init(loadChartRef.value);
  loadChart.setOption({
    color: ["#1976d2", "#1f7a68"],
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["sRPE", "跑量"] },
    grid: { left: 48, right: 44, top: 48, bottom: 40 },
    xAxis: {
      type: "category",
      data: trendItems.value.map((item) => item.load_date.slice(5)),
      axisTick: { show: false },
    },
    yAxis: [
      { type: "value", name: "sRPE", splitLine: { lineStyle: { color: "#e5e7eb" } } },
      { type: "value", name: "km", splitLine: { show: false } },
    ],
    series: [
      {
        name: "sRPE",
        type: "line",
        smooth: true,
        connectNulls: false,
        data: trendItems.value.map((item) => item.srpe_load_au),
      },
      {
        name: "跑量",
        type: "bar",
        yAxisIndex: 1,
        barMaxWidth: 26,
        data: trendItems.value.map((item) => item.distance_km),
      },
    ],
  });
}

async function reload() {
  loading.value = true;
  try {
    await loadToday();
    await loadTrend();
  } finally {
    loading.value = false;
  }
}

async function saveCheckin() {
  savingCheckin.value = true;
  try {
    await saveTodayRecoveryCheckin(checkinForm);
    await recalculateReadiness();
    trackUsageEvent("readiness_recalculated", { source: "recovery_checkin" });
    checkinDialogVisible.value = false;
    ElMessage.success("恢复状态已保存");
    trackUsageEvent("recovery_checkin_saved", { source: "training_readiness" });
    await reload();
  } finally {
    savingCheckin.value = false;
  }
}

function resizeCharts() {
  loadChart?.resize();
}

onMounted(async () => {
  trackUsageEvent("readiness_detail_viewed");
  await reload();
  window.addEventListener("resize", resizeCharts);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeCharts);
  loadChart?.dispose();
  loadChart = null;
});
</script>

<style scoped>
.readiness-page {
  gap: 16px;
}

.status-body {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(260px, 1fr) minmax(260px, 1fr);
  gap: 18px;
}

.status-copy,
.info-list,
.signal-list {
  display: grid;
  gap: 10px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

.status-copy strong {
  color: var(--text);
  font-size: 24px;
}

.status-list h3 {
  margin: 0 0 8px;
  color: var(--text);
  font-size: 14px;
}

.status-list ul {
  display: grid;
  gap: 7px;
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

.readiness-metrics {
  grid-template-columns: repeat(6, minmax(130px, 1fr));
}

.readiness-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.signal-list :deep(.el-empty) {
  padding: 6px 0;
}

.medical-note,
.chart-note {
  margin: 0;
  color: #7a4d12;
  font-size: 12px;
  line-height: 1.7;
}

.chart {
  width: 100%;
  height: 320px;
}

.privacy-alert {
  margin-bottom: 14px;
}

.checkin-form {
  min-width: 0;
}

.readiness-tag {
  border-radius: 999px;
  font-weight: 700;
}

.readiness-normal {
  --el-tag-text-color: #167247;
  --el-tag-border-color: #a9dec4;
  --el-tag-bg-color: var(--green-soft);
}

.readiness-watch {
  --el-tag-text-color: #9a6516;
  --el-tag-border-color: #efd59e;
  --el-tag-bg-color: var(--yellow-soft);
}

.readiness-reduce_load {
  --el-tag-text-color: #a23434;
  --el-tag-border-color: #efbbbb;
  --el-tag-bg-color: #fff0f0;
}

.readiness-insufficient_data {
  --el-tag-text-color: #1f4e79;
  --el-tag-border-color: #b5d2e8;
  --el-tag-bg-color: var(--blue-soft);
}

@media (max-width: 1100px) {
  .readiness-metrics {
    grid-template-columns: repeat(3, minmax(130px, 1fr));
  }

  .status-body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .readiness-grid,
  .readiness-metrics {
    grid-template-columns: 1fr;
  }

  .chart {
    height: 260px;
  }
}
</style>
