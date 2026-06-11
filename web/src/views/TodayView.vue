<template>
  <div class="page-stack">
    <div class="excel-section-title">今日训练</div>
    <div class="excel-subtitle">
      第一次使用可以先通过 AI 生成训练计划，或导入自己的 Excel 训练计划。训练完成后，在今日训练中填写日志，系统会自动统计完成情况。
    </div>

    <section v-if="showOnboarding" class="onboarding-card">
      <div class="onboarding-copy">
        <div class="onboarding-kicker">首次使用</div>
        <h3>欢迎使用 GaitLogic Planner</h3>
        <p>先选择一种方式建立你的第一份训练计划。导入现有 Excel 更快，AI 制定计划适合从目标赛事开始生成草稿。</p>
      </div>
      <div class="onboarding-actions">
        <button class="start-option excel-option" type="button" @click="router.push('/excel-import')">
          <span class="start-option-icon">XLS</span>
          <strong>用 Excel 导入</strong>
          <em>下载标准模板，填写训练周期、训练计划和配速规则后上传。</em>
        </button>
        <button class="start-option ai-option" type="button" @click="router.push('/ai-plan')">
          <span class="start-option-icon">AI</span>
          <strong>用 AI 制定计划</strong>
          <em>输入当前能力、目标赛事和训练偏好，先生成可编辑草稿。</em>
        </button>
      </div>
    </section>

    <div class="toolbar">
      <el-date-picker v-model="today" value-format="YYYY-MM-DD" type="date" @change="load" />
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="panel">
      <el-table class="desktop-workout-table" :data="workouts" v-loading="loading" empty-text="今天还没有训练计划">
        <el-table-column prop="workout_date" label="日期" width="120" />
        <el-table-column prop="weekday" label="星期" width="90" />
        <el-table-column prop="planned_content" label="今日计划" min-width="260" />
        <el-table-column prop="planned_distance_km" label="计划 km" width="110" />
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag :class="statusClass(row.workout_log?.status_normalized)" effect="plain">
              {{ labelFor(statusOptions, row.workout_log?.status_normalized) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" :icon="EditPen" @click="goLog(row.id)">
              填写日志
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="mobile-workout-list" v-loading="loading">
        <article v-for="row in workouts" :key="row.id" class="workout-card">
          <div class="workout-card-head">
            <div>
              <strong>{{ row.workout_date || today }}</strong>
              <span>{{ row.weekday || "-" }}</span>
            </div>
            <el-tag :class="statusClass(row.workout_log?.status_normalized)" effect="plain">
              {{ labelFor(statusOptions, row.workout_log?.status_normalized) }}
            </el-tag>
          </div>
          <p>{{ row.planned_content }}</p>
          <div class="workout-card-meta">
            <span>{{ row.planned_distance_km || 0 }} km</span>
            <el-button type="primary" size="small" :icon="EditPen" @click="goLog(row.id)">填写日志</el-button>
          </div>
        </article>
        <el-empty v-if="!loading && workouts.length === 0" description="今天还没有训练计划" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { EditPen, Refresh } from "@element-plus/icons-vue";

import { listTodayWorkouts } from "@/api/plannedWorkouts";
import { listTrainingCycles } from "@/api/trainingCycles";
import type { PlannedWorkout, TrainingCycle, WorkoutStatusNormalized } from "@/types/models";
import { labelFor, statusOptions } from "@/types/options";

const router = useRouter();
const today = ref(new Date().toISOString().slice(0, 10));
const workouts = ref<PlannedWorkout[]>([]);
const cycles = ref<TrainingCycle[]>([]);
const loading = ref(false);
const loadingCycles = ref(true);
const showOnboarding = computed(() => !loadingCycles.value && cycles.value.length === 0);

async function load() {
  loading.value = true;
  try {
    workouts.value = await listTodayWorkouts(today.value);
  } finally {
    loading.value = false;
  }
}

async function loadCycles() {
  loadingCycles.value = true;
  try {
    cycles.value = await listTrainingCycles();
  } finally {
    loadingCycles.value = false;
  }
}

function goLog(id: number) {
  router.push(`/workouts/${id}/log`);
}

function statusClass(status?: WorkoutStatusNormalized | null) {
  if (status?.startsWith("completed")) return "status-tag status-done";
  if (status === "missed" || status === "skipped") return "status-tag status-alert";
  if (status === "rest" || status === "rest_or_cancelled") return "status-tag status-rest";
  return "status-tag status-pending";
}

onMounted(() => {
  loadCycles();
  load();
});
</script>

<style scoped>
.onboarding-card {
  display: grid;
  grid-template-columns: minmax(260px, 0.78fr) minmax(360px, 1fr);
  gap: 26px;
  align-items: stretch;
  padding: 30px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background:
    radial-gradient(circle at 18% 10%, rgba(25, 118, 210, 0.08), transparent 28%),
    #ffffff;
  box-shadow: var(--shadow-sm);
}

.onboarding-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.onboarding-kicker {
  margin-bottom: 8px;
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.onboarding-card h3 {
  margin: 0;
  color: #172033;
  font-size: 26px;
  line-height: 1.2;
}

.onboarding-card p {
  margin: 10px 0 0;
  color: #667085;
  line-height: 1.7;
}

.onboarding-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.start-option {
  min-height: 168px;
  padding: 18px;
  border: 1px solid #dbe6f3;
  border-radius: 8px;
  background: #fbfdff;
  color: #172033;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
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

.mobile-workout-list {
  display: none;
}

@media (max-width: 768px) {
  .onboarding-card,
  .onboarding-actions {
    grid-template-columns: 1fr;
  }

  .onboarding-card {
    gap: 16px;
    margin: 0 12px;
    padding: 18px;
  }

  .onboarding-card h3 {
    font-size: 21px;
  }

  .start-option {
    min-height: auto;
    padding: 14px;
  }

  .start-option-icon {
    margin-bottom: 12px;
  }

  .desktop-workout-table {
    display: none;
  }

  .mobile-workout-list {
    display: grid;
    gap: 10px;
    padding: 12px;
  }

  .workout-card {
    display: grid;
    gap: 10px;
    padding: 14px;
    border: 1px solid #d8dde3;
    border-radius: 6px;
    background: #ffffff;
  }

  .workout-card-head,
  .workout-card-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .workout-card-head div {
    display: grid;
    gap: 3px;
  }

  .workout-card-head span,
  .workout-card-meta span {
    color: #667085;
    font-size: 12px;
  }

  .workout-card p {
    margin: 0;
    color: #172033;
    line-height: 1.6;
  }
}
</style>
