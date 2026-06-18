<template>
  <div class="page-stack">
    <PageHeader
      title="今日训练"
      :subtitle="showOnboarding ? '第一次使用：你的训练课表还在等待创建或分配。课表准备好后，今天的训练会显示在这里。' : undefined"
    />
    <div v-if="!showOnboarding" class="daily-advice">
      <div>
        <strong>今日训练建议</strong>
        <p>当前请按今日课表完成训练，并结合身体感受合理调整强度。</p>
      </div>
      <span>疲劳管理接入后，将在这里提供个性化建议</span>
      <el-button v-if="showWeeklyReviewPrompt" type="primary" plain @click="router.push('/weekly-review')">查看周复盘</el-button>
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
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <div class="workout-actions">
              <el-button
                type="primary"
                size="small"
                title="按计划完成"
                @click="openQuickCheckin(row, 'completed_normal')"
              >
                完成
              </el-button>
              <el-button
                size="small"
                title="调整后完成"
                @click="openQuickCheckin(row, 'completed_adjusted')"
              >
                调整
              </el-button>
              <el-button size="small" :icon="EditPen" title="填写更多日志" @click="goLog(row.id)">更多</el-button>
            </div>
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
            <div class="workout-actions mobile-actions">
              <el-button
                type="primary"
                size="small"
                title="按计划完成"
                @click="openQuickCheckin(row, 'completed_normal')"
              >
                完成
              </el-button>
              <el-button
                size="small"
                title="调整后完成"
                @click="openQuickCheckin(row, 'completed_adjusted')"
              >
                调整
              </el-button>
              <el-button size="small" :icon="EditPen" title="填写更多日志" @click="goLog(row.id)">更多</el-button>
            </div>
          </div>
        </article>
        <el-empty v-if="!loading && workouts.length === 0" description="今天还没有训练计划" />
      </div>
    </div>

    <el-dialog v-model="quickDialogVisible" title="快速训练打卡" width="560px">
      <el-form label-position="top" class="quick-form">
        <div class="form-grid">
          <el-form-item label="完成状态">
            <el-select v-model="quickForm.status_normalized" style="width: 100%">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="实际距离 km">
            <el-input-number v-model="quickForm.actual_distance_km" :precision="2" :min="0" style="width: 100%" />
          </el-form-item>
          <el-form-item label="实际时长">
            <el-time-picker
              v-model="quickDuration"
              format="HH:mm:ss"
              value-format="HH:mm:ss"
              :default-value="new Date(2000, 0, 1, 0, 0, 0)"
              placeholder="时:分:秒"
              style="width: 100%"
            />
            <div v-if="autoPaceText" class="form-help">自动估算均配：{{ autoPaceText }}，也可以在“记录更多数据”中手动覆盖。</div>
          </el-form-item>
          <el-form-item>
            <template #label>RPE <RpeHelp /></template>
            <el-input-number v-model="quickForm.rpe" :min="0" :max="10" style="width: 100%" />
          </el-form-item>
        </div>
        <el-form-item label="一句感受">
          <el-input v-model="quickForm.review_note" type="textarea" :rows="2" placeholder="例如：整体轻松，后半程略热" />
        </el-form-item>
        <el-collapse>
          <el-collapse-item title="记录更多数据" name="more">
            <div class="form-grid">
              <el-form-item label="平均配速">
                <el-time-picker
                  v-model="quickPace"
                  format="mm:ss"
                  value-format="HH:mm:ss"
                  :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                  placeholder="分:秒 /km"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="平均心率">
                <el-input-number v-model="quickForm.avg_heart_rate" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="睡眠 h">
                <el-input-number v-model="quickForm.sleep_hours" :precision="1" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="HRV">
                <el-input-number v-model="quickForm.hrv" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="晨脉">
                <el-input-number v-model="quickForm.morning_heart_rate" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="体重 kg">
                <el-input-number v-model="quickForm.weight_kg" :precision="1" :min="0" style="width: 100%" />
              </el-form-item>
              <el-form-item label="腿感">
                <el-input v-model="quickForm.leg_feeling" />
              </el-form-item>
              <el-form-item label="疼痛部位">
                <el-input v-model="quickForm.pain_location" />
              </el-form-item>
              <el-form-item label="疼痛等级">
                <el-slider v-model="painLevel" :min="0" :max="5" show-stops />
              </el-form-item>
            </div>
            <el-form-item label="明日调整">
              <el-input v-model="quickForm.tomorrow_adjustment" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="训练警报">
              <el-input v-model="quickForm.alert_message" type="textarea" :rows="2" />
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="quickDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingQuick" @click="saveQuickCheckin">保存打卡</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { EditPen, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import RpeHelp from "@/components/RpeHelp.vue";
import { listTodayWorkouts } from "@/api/plannedWorkouts";
import { listTrainingCycles } from "@/api/trainingCycles";
import { listTrainingBlocks } from "@/api/trainingBlocks";
import { updateWorkoutLog } from "@/api/workoutLogs";
import { trackUsageEvent } from "@/api/usageEvents";
import type { PlannedWorkout, TrainingBlock, TrainingCycle, WorkoutLogPayload, WorkoutStatusNormalized } from "@/types/models";
import { labelFor, statusOptions } from "@/types/options";

const router = useRouter();
const today = ref(new Date().toISOString().slice(0, 10));
const workouts = ref<PlannedWorkout[]>([]);
const cycles = ref<TrainingCycle[]>([]);
const blocks = ref<TrainingBlock[]>([]);
const loading = ref(false);
const loadingCycles = ref(true);
const quickDialogVisible = ref(false);
const savingQuick = ref(false);
const quickWorkout = ref<PlannedWorkout | null>(null);
const quickForm = reactive<WorkoutLogPayload>(initialQuickForm());
const showOnboarding = computed(() => !loadingCycles.value && cycles.value.length === 0);
const showWeeklyReviewPrompt = computed(() =>
  blocks.value.some((block) => block.end_date && block.end_date < today.value),
);
const painLevel = computed({
  get: () => quickForm.pain_level ?? 0,
  set: (value: number) => {
    quickForm.pain_level = value;
  },
});
const quickDuration = computed({
  get: () => secondsToTime(quickForm.actual_duration_seconds),
  set: (value: string | null) => {
    quickForm.actual_duration_seconds = timeToSeconds(value);
  },
});
const quickPace = computed({
  get: () => secondsToTime(quickForm.avg_pace_seconds_per_km),
  set: (value: string | null) => {
    quickForm.avg_pace_seconds_per_km = timeToSeconds(value);
  },
});
const autoPaceText = computed(() => {
  const distance = Number(quickForm.actual_distance_km || 0);
  const duration = Number(quickForm.actual_duration_seconds || 0);
  if (!distance || !duration || distance <= 0) return "";
  const seconds = Math.round(duration / distance);
  const minutes = Math.floor(seconds / 60);
  const restSeconds = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${restSeconds}/km`;
});

watch(
  () => [quickForm.actual_distance_km, quickForm.actual_duration_seconds],
  ([distanceValue, durationValue]) => {
    const distance = Number(distanceValue || 0);
    const duration = Number(durationValue || 0);
    quickForm.avg_pace_seconds_per_km = distance > 0 && duration > 0 ? Math.round(duration / distance) : null;
  },
);

function secondsToTime(value?: number | null) {
  if (value == null) return "00:00:00";
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = value % 60;
  return [hours, minutes, seconds].map((item) => String(item).padStart(2, "0")).join(":");
}

function timeToSeconds(value?: string | null) {
  if (!value) return null;
  const [hours, minutes, seconds] = value.split(":").map(Number);
  return hours * 3600 + minutes * 60 + seconds;
}

function initialQuickForm(): WorkoutLogPayload {
  return {
    status_normalized: "completed_normal",
    actual_distance_km: 0,
    actual_duration_seconds: null,
    avg_pace_seconds_per_km: null,
    avg_heart_rate: null,
    rpe: null,
    i_effective_km: null,
    t1_effective_km: null,
    t2_effective_km: null,
    m_effective_km: null,
    r_effective_km: null,
    sleep_hours: null,
    hrv: null,
    morning_heart_rate: null,
    weight_kg: null,
    leg_feeling: null,
    pain_location: null,
    pain_level: 0,
    main_session_data: null,
    review_note: null,
    tomorrow_adjustment: null,
    alert_message: null,
  };
}

function resetQuickForm() {
  Object.assign(quickForm, initialQuickForm());
}

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
    const blockGroups = await Promise.all(cycles.value.map((cycle) => listTrainingBlocks(cycle.id)));
    blocks.value = blockGroups.flat();
  } finally {
    loadingCycles.value = false;
  }
}

function goLog(id: number) {
  router.push(`/workouts/${id}/log`);
}

function openQuickCheckin(row: PlannedWorkout, status: "completed_normal" | "completed_adjusted") {
  quickWorkout.value = row;
  resetQuickForm();
  Object.assign(quickForm, row.workout_log || {});
  quickForm.status_normalized = status;
  quickForm.actual_distance_km = status === "completed_normal" ? Number(row.planned_distance_km || 0) : null;
  quickForm.review_note = status === "completed_adjusted" ? quickForm.review_note || "调整后完成。" : quickForm.review_note;
  quickDialogVisible.value = true;
  trackUsageEvent("workout_quick_checkin_opened", { planned_workout_id: row.id });
}

async function saveQuickCheckin() {
  if (!quickWorkout.value) return;
  savingQuick.value = true;
  try {
    await updateWorkoutLog(quickWorkout.value.id, quickForm);
    ElMessage.success("训练已打卡");
    quickDialogVisible.value = false;
    trackUsageEvent("workout_log_saved", { planned_workout_id: quickWorkout.value.id });
    await load();
  } finally {
    savingQuick.value = false;
  }
}

function statusClass(status?: WorkoutStatusNormalized | null) {
  if (status?.startsWith("completed")) return "status-tag status-done";
  if (status === "missed" || status === "skipped") return "status-tag status-alert";
  if (status === "rest" || status === "rest_or_cancelled") return "status-tag status-rest";
  return "status-tag status-pending";
}

onMounted(() => {
  trackUsageEvent("today_viewed");
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
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background:
    radial-gradient(circle at 18% 10%, rgba(25, 118, 210, 0.08), transparent 28%),
    #ffffff;
  box-shadow: var(--card-shadow);
}

.daily-advice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px;
  border: 1px solid var(--card-border);
  border-left: 3px solid var(--primary);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.daily-advice strong {
  color: var(--text);
  font-size: 15px;
}

.daily-advice p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
}

.daily-advice span {
  flex: 0 0 auto;
  color: var(--muted);
  font-size: 12px;
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

.mobile-workout-list {
  display: none;
}

.workout-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.workout-actions :deep(.el-button) {
  margin-left: 0;
  padding: 5px 8px;
}

.form-help {
  margin-top: 6px;
  color: #667085;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .daily-advice {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

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
    box-shadow: var(--card-shadow);
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

  .mobile-actions {
    flex: 1;
    justify-content: flex-end;
    min-width: 0;
  }

  .mobile-actions :deep(.el-button) {
    min-width: 46px;
    padding: 5px 7px;
  }
}
</style>
