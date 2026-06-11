<template>
  <div class="page-stack calendar-page">
    <div class="page-title-row">
      <div>
        <div class="excel-section-title">训练日历</div>
        <div class="excel-subtitle">按月查看每日计划和完成情况，点击日期可查看日志摘要。</div>
      </div>
      <el-button type="primary" :icon="EditPen" :disabled="!selectedDay?.planned_workout_id" @click="editSelectedLog">
        编辑日志
      </el-button>
    </div>

    <div class="toolbar calendar-toolbar">
      <div class="filter-row">
        <el-date-picker v-model="month" type="month" value-format="YYYY-MM" placeholder="选择月份" @change="load" />
        <el-select v-model="cycleId" clearable placeholder="全部训练周期" style="width: 220px" @change="load">
          <el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" />
        </el-select>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <section class="calendar-summary">
      <div class="metric-card">
        <p class="metric-label">计划跑量</p>
        <div class="metric-value">{{ formatKm(calendar?.summary.planned_distance_km) }}</div>
      </div>
      <div class="metric-card">
        <p class="metric-label">已完成跑量</p>
        <div class="metric-value">{{ formatKm(calendar?.summary.actual_distance_km) }}</div>
      </div>
      <div class="metric-card">
        <p class="metric-label">完成率</p>
        <div class="metric-value">{{ formatPercent(calendar?.summary.completion_rate) }}</div>
      </div>
      <div class="metric-card">
        <p class="metric-label">完成天数</p>
        <div class="metric-value">{{ calendar?.summary.completed_days ?? 0 }}</div>
      </div>
      <div class="metric-card">
        <p class="metric-label">未完成天数</p>
        <div class="metric-value">{{ calendar?.summary.missed_days ?? 0 }}</div>
      </div>
    </section>

    <section class="calendar-layout">
      <article class="panel calendar-panel" v-loading="loading">
        <div class="weekday-grid">
          <span v-for="weekday in weekdays" :key="weekday">{{ weekday }}</span>
        </div>
        <div class="month-grid">
          <div v-for="blank in leadingBlankCount" :key="`blank-${blank}`" class="calendar-cell is-blank" />
          <button
            v-for="day in calendar?.days || []"
            :key="day.date"
            type="button"
            class="calendar-cell"
            :class="[
              statusClass(day.status_normalized),
              { selected: selectedDay?.date === day.date, 'is-today': day.date === todayString },
            ]"
            @click="selectedDay = day"
          >
            <span class="day-number">{{ Number(day.date.slice(8, 10)) }}</span>
            <span v-if="day.date === todayString" class="today-badge">今天</span>
            <span class="day-status">{{ statusSymbol(day.status_normalized) }}</span>
            <strong>{{ shortMainType(day.main_type) }}</strong>
            <em v-if="day.planned_distance_km">{{ Number(day.planned_distance_km).toFixed(1) }}km</em>
          </button>
        </div>
      </article>

      <aside class="panel detail-panel">
        <div class="panel-head">
          <div>
            <h3>{{ selectedDay?.date || "选择日期" }}</h3>
            <p>{{ selectedDay?.weekday || "点击日历中的一天查看详情" }}</p>
          </div>
          <span v-if="selectedDay" class="detail-status" :class="statusClass(selectedDay.status_normalized)">
            {{ statusSymbol(selectedDay.status_normalized) || "空" }}
          </span>
        </div>

        <template v-if="selectedDay">
          <dl class="detail-list">
            <div>
              <dt>计划内容</dt>
              <dd>{{ selectedDay.planned_content || "休息 / 无训练计划" }}</dd>
            </div>
            <div>
              <dt>实际距离</dt>
              <dd>{{ selectedDay.actual_distance_km ? `${selectedDay.actual_distance_km} km` : "-" }}</dd>
            </div>
            <div>
              <dt>均配</dt>
              <dd>{{ formatPace(selectedDay.avg_pace_seconds_per_km) }}</dd>
            </div>
            <div>
              <dt>均心率</dt>
              <dd>{{ selectedDay.avg_heart_rate || "-" }}</dd>
            </div>
            <div>
              <dt>RPE</dt>
              <dd>{{ selectedDay.rpe ?? "-" }}</dd>
            </div>
            <div class="full">
              <dt>一句复盘</dt>
              <dd>{{ selectedDay.review_note || "-" }}</dd>
            </div>
          </dl>
          <el-button
            type="primary"
            :icon="EditPen"
            :disabled="!selectedDay.planned_workout_id"
            @click="editSelectedLog"
          >
            编辑日志
          </el-button>
        </template>
        <el-empty v-else description="请选择一个日期" />
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { EditPen, Refresh } from "@element-plus/icons-vue";

import { getTrainingCalendar } from "@/api/trainingCalendar";
import { listTrainingCycles } from "@/api/trainingCycles";
import type {
  TrainingCalendarDay,
  TrainingCalendarResult,
  TrainingCycle,
  WorkoutMainTypeNormalized,
  WorkoutStatusNormalized,
} from "@/types/models";

const router = useRouter();
const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const todayString = formatLocalDate(new Date());
const month = ref(todayString.slice(0, 7));
const cycleId = ref<number | null>(null);
const cycles = ref<TrainingCycle[]>([]);
const calendar = ref<TrainingCalendarResult | null>(null);
const selectedDay = ref<TrainingCalendarDay | null>(null);
const loading = ref(false);

function formatLocalDate(value: Date) {
  const year = value.getFullYear();
  const monthValue = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${monthValue}-${day}`;
}

const leadingBlankCount = computed(() => {
  const firstDay = calendar.value?.days[0]?.date;
  if (!firstDay) return 0;
  const [year, monthValue, day] = firstDay.split("-").map(Number);
  const jsDay = new Date(year, monthValue - 1, day).getDay();
  return jsDay === 0 ? 6 : jsDay - 1;
});

async function load() {
  loading.value = true;
  try {
    calendar.value = await getTrainingCalendar({ month: month.value, cycle_id: cycleId.value });
    selectedDay.value = calendar.value.days.find((day) => day.planned_workout_id) || calendar.value.days[0] || null;
  } finally {
    loading.value = false;
  }
}

function editSelectedLog() {
  if (!selectedDay.value?.planned_workout_id) return;
  router.push(`/workouts/${selectedDay.value.planned_workout_id}/log`);
}

function statusSymbol(status: WorkoutStatusNormalized) {
  const symbols: Record<WorkoutStatusNormalized, string> = {
    completed_high: "✓✓",
    completed_normal: "✓",
    completed_adjusted: "△",
    missed: "×",
    rest: "休",
    rest_or_cancelled: "休",
    skipped: "×",
    not_started: "",
    unknown: "",
  };
  return symbols[status] || "";
}

function statusClass(status: WorkoutStatusNormalized) {
  if (status === "completed_high" || status === "completed_normal") return "is-done";
  if (status === "completed_adjusted") return "is-adjusted";
  if (status === "missed" || status === "skipped") return "is-missed";
  if (status === "rest" || status === "rest_or_cancelled") return "is-rest";
  return "is-pending";
}

function shortMainType(type?: WorkoutMainTypeNormalized | null) {
  const labels: Partial<Record<WorkoutMainTypeNormalized, string>> = {
    easy: "E",
    easy_with_speed: "E+S",
    interval_speed: "I/R",
    tempo: "T",
    recovery: "REC",
    long_run: "L",
    rest: "休",
    mixed: "Mix",
  };
  return type ? labels[type] || "" : "";
}

function formatKm(value?: number | string | null) {
  return `${Number(value || 0).toFixed(1)} km`;
}

function formatPercent(value?: number | string | null) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function formatPace(seconds?: number | null) {
  if (!seconds) return "-";
  const minute = Math.floor(seconds / 60);
  const second = seconds % 60;
  return `${minute}:${String(second).padStart(2, "0")}/km`;
}

onMounted(async () => {
  cycles.value = await listTrainingCycles();
  await load();
});
</script>

<style scoped>
.calendar-page {
  gap: 14px;
}

.page-title-row,
.calendar-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: start;
}

.calendar-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 10px;
}

.calendar-layout {
  grid-template-columns: minmax(0, 1fr) 340px;
}

.calendar-panel,
.detail-panel {
  padding: 16px;
}

.weekday-grid,
.month-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 6px;
}

.weekday-grid {
  margin-bottom: 8px;
  color: #667085;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}

.calendar-cell {
  position: relative;
  display: grid;
  align-content: start;
  min-height: 96px;
  padding: 9px;
  border: 1px solid #d8dde3;
  border-radius: 6px;
  color: #172033;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
}

.calendar-cell.is-blank {
  border-color: transparent;
  background: transparent;
  cursor: default;
}

.calendar-cell.selected {
  border-color: #1976d2;
  box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.14);
}

.calendar-cell.is-today {
  border-color: #ff8a00;
  background: linear-gradient(180deg, #fff7ec 0%, #ffffff 70%);
  box-shadow: inset 0 0 0 2px rgba(255, 138, 0, 0.36);
}

.calendar-cell.is-today.selected {
  box-shadow:
    inset 0 0 0 2px rgba(255, 138, 0, 0.42),
    0 0 0 2px rgba(25, 118, 210, 0.18);
}

.day-number {
  font-weight: 750;
}

.day-status {
  position: absolute;
  top: 8px;
  right: 8px;
  font-weight: 800;
}

.today-badge {
  position: absolute;
  right: 7px;
  bottom: 7px;
  padding: 2px 6px;
  border-radius: 999px;
  color: #ffffff;
  background: #ff8a00;
  font-size: 11px;
  font-weight: 800;
}

.calendar-cell strong {
  margin-top: 14px;
  color: #1976d2;
  font-size: 13px;
}

.calendar-cell em {
  margin-top: 4px;
  color: #667085;
  font-size: 12px;
  font-style: normal;
}

.is-done {
  background: #f0fbf5;
}

.is-adjusted {
  background: #fff8e8;
}

.is-missed {
  background: #fff1f1;
}

.is-rest {
  color: #7a4d12;
  background: #fffaf0;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head h3 {
  margin: 0;
  font-size: 18px;
}

.panel-head p {
  margin: 5px 0 0;
  color: #667085;
  font-size: 13px;
}

.detail-status {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  font-weight: 800;
}

.detail-list {
  display: grid;
  gap: 12px;
  margin: 0 0 16px;
}

.detail-list div {
  display: grid;
  gap: 4px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf0f3;
}

.detail-list dt {
  color: #667085;
  font-size: 12px;
}

.detail-list dd {
  margin: 0;
  color: #172033;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .calendar-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .calendar-layout,
  .page-title-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .calendar-panel,
  .detail-panel {
    padding: 12px;
  }

  .weekday-grid,
  .month-grid {
    gap: 4px;
  }

  .calendar-cell {
    min-height: 70px;
    padding: 6px;
  }

  .calendar-cell strong {
    margin-top: 9px;
    font-size: 12px;
  }

  .calendar-cell em {
    display: none;
  }

  .day-status {
    top: 5px;
    right: 5px;
  }

  .today-badge {
    right: 5px;
    bottom: 5px;
    padding: 1px 5px;
    font-size: 10px;
  }
}
</style>
