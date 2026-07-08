<template>
  <div class="page-stack">
    <PageHeader title="训练日志" subtitle="实际完成记录、RPE、疼痛、主课数据和第二天调整统一在这里填写。" />

    <div class="toolbar">
      <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
      <el-button type="primary" :icon="Check" @click="submit">{{ submitLabel }}</el-button>
    </div>

    <el-alert
      v-if="isDevicePrefilled"
      title="已同步设备客观数据，补充 RPE、疼痛、腿感和复盘即可。"
      type="success"
      show-icon
      :closable="false"
    />

    <section v-if="isDevicePrefilled && deviceMetricRows.length" class="device-metrics">
      <div v-for="item in deviceMetricRows" :key="item.label">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </section>

    <div class="panel">
      <div class="panel-header">
        <h2 class="panel-title">训练日志</h2>
      </div>
      <div class="panel-body">
        <el-form label-width="118px" v-loading="loading">
          <div class="form-grid">
            <el-form-item label="完成状态">
              <el-select v-model="form.status_normalized" style="width: 100%">
                <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="!isDevicePrefilled" label="实际 km">
              <el-input-number v-model="form.actual_distance_km" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item v-if="!isDevicePrefilled" label="实际时长">
              <el-time-picker
                v-model="durationText"
                format="HH:mm:ss"
                value-format="HH:mm:ss"
                :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                placeholder="时:分:秒"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item v-if="!isDevicePrefilled" label="平均配速">
              <el-time-picker
                v-model="paceText"
                format="mm:ss"
                value-format="HH:mm:ss"
                :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                placeholder="分:秒 /km"
                style="width: 100%"
              />
              <div v-if="autoPaceText" class="form-help">根据实际距离和时长自动估算：{{ autoPaceText }}</div>
            </el-form-item>
            <el-form-item v-if="!isDevicePrefilled" label="均心率">
              <el-input-number v-model="form.avg_heart_rate" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <template #label>RPE <RpeHelp /></template>
              <el-input-number v-model="form.rpe" :min="0" :max="10" style="width: 100%" />
            </el-form-item>
            <el-form-item label="主课数据" class="full">
              <el-input v-model="form.main_session_data" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="一句复盘" class="full">
              <el-input v-model="form.review_note" type="textarea" :rows="2" />
            </el-form-item>
          </div>
          <el-collapse class="advanced-collapse">
            <el-collapse-item title="高级字段" name="advanced">
              <div class="form-grid">
                <el-form-item label="原始状态">
                  <el-input v-model="form.status_raw" />
                </el-form-item>
                <el-form-item label="完成率">
                  <el-input-number v-model="form.completion_rate" :precision="1" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="I 有效 km">
                  <el-input-number v-model="form.i_effective_km" :precision="2" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="T1 有效 km">
                  <el-input-number v-model="form.t1_effective_km" :precision="2" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="T2 有效 km">
                  <el-input-number v-model="form.t2_effective_km" :precision="2" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="M 有效 km">
                  <el-input-number v-model="form.m_effective_km" :precision="2" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="R 有效 km">
                  <el-input-number v-model="form.r_effective_km" :precision="2" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="睡眠小时">
                  <el-input-number v-model="form.sleep_hours" :precision="1" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="HRV">
                  <el-input-number v-model="form.hrv" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="晨脉">
                  <el-input-number v-model="form.morning_heart_rate" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="体重 kg">
                  <el-input-number v-model="form.weight_kg" :precision="1" :min="0" style="width: 100%" />
                </el-form-item>
                <el-form-item label="腿感">
                  <el-input v-model="form.leg_feeling" />
                </el-form-item>
                <el-form-item label="疼痛部位">
                  <el-input v-model="form.pain_location" />
                </el-form-item>
                <el-form-item label="疼痛等级">
                  <el-slider v-model="painLevel" :min="0" :max="10" show-stops />
                </el-form-item>
                <el-form-item label="明日调整" class="full">
                  <el-input v-model="form.tomorrow_adjustment" type="textarea" :rows="2" />
                </el-form-item>
                <el-form-item label="训练警报" class="full">
                  <el-input v-model="form.alert_message" type="textarea" :rows="2" />
                </el-form-item>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, Check } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import RpeHelp from "@/components/RpeHelp.vue";
import { getWorkoutCompletionContext, getWorkoutLog, updateWorkoutLog } from "@/api/workoutLogs";
import type { WorkoutCompletionContext, WorkoutLogPayload } from "@/types/models";
import { statusOptions } from "@/types/options";

const route = useRoute();
const router = useRouter();
const plannedWorkoutId = Number(route.params.id);
const loading = ref(false);
const pauseAutoPace = ref(false);
const completionMode = ref("manual_full");
const completionContext = ref<WorkoutCompletionContext | null>(null);
const form = reactive<WorkoutLogPayload>({
  status_raw: null,
  status_normalized: "not_started",
  pain_level: 0,
});

const painLevel = computed({
  get: () => form.pain_level ?? 0,
  set: (value: number) => {
    form.pain_level = value;
  },
});
const durationText = computed({
  get: () => secondsToTime(form.actual_duration_seconds),
  set: (value: string | null) => {
    form.actual_duration_seconds = timeToSeconds(value);
  },
});
const paceText = computed({
  get: () => secondsToTime(form.avg_pace_seconds_per_km),
  set: (value: string | null) => {
    form.avg_pace_seconds_per_km = timeToSeconds(value);
  },
});
const autoPaceText = computed(() => formatPace(form.avg_pace_seconds_per_km));
const isDevicePrefilled = computed(() => ["device_prefilled", "garmin_prefilled"].includes(completionMode.value));
const submitLabel = computed(() =>
  isDevicePrefilled.value ? "确认完成并补充训练感受" : "提交日志",
);
const deviceMetricRows = computed(() => {
  const fields = completionContext.value?.prefilled_objective_fields || {};
  return [
    { label: "实际距离", value: fields.actual_distance_km ? `${fields.actual_distance_km} km` : "" },
    { label: "实际时长", value: fields.actual_duration_seconds ? formatDuration(Number(fields.actual_duration_seconds)) : "" },
    { label: "平均配速", value: fields.avg_pace_seconds_per_km ? formatPace(Number(fields.avg_pace_seconds_per_km)) : "" },
    { label: "平均心率", value: fields.avg_heart_rate ? `${fields.avg_heart_rate}` : "" },
  ].filter((item) => item.value);
});

watch(
  () => [form.actual_distance_km, form.actual_duration_seconds],
  ([distanceValue, durationValue]) => {
    if (pauseAutoPace.value) return;
    const distance = Number(distanceValue || 0);
    const duration = Number(durationValue || 0);
    form.avg_pace_seconds_per_km = distance > 0 && duration > 0 ? Math.round(duration / distance) : null;
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

function formatPace(value?: number | null) {
  if (!value) return "";
  const minutes = Math.floor(value / 60);
  return `${minutes}:${String(value % 60).padStart(2, "0")}/km`;
}

function formatDuration(value?: number | null) {
  if (!value) return "";
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = value % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

async function load() {
  loading.value = true;
  pauseAutoPace.value = true;
  try {
    const context = await getWorkoutCompletionContext(plannedWorkoutId);
    completionContext.value = context;
    completionMode.value = context.mode;
    const log = context.existing_workout_log || await getWorkoutLog(plannedWorkoutId);
    Object.assign(form, log);
  } finally {
    await nextTick();
    pauseAutoPace.value = false;
    loading.value = false;
  }
}

async function submit() {
  await updateWorkoutLog(plannedWorkoutId, form);
  ElMessage.success("训练日志已保存");
}

onMounted(load);
</script>

<style scoped>
.advanced-collapse {
  margin-top: 8px;
}

.device-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.device-metrics > div {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.device-metrics span {
  color: var(--muted);
  font-size: 12px;
}

.device-metrics strong {
  color: var(--text);
  font-size: 16px;
}

.form-help {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .device-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 0 12px;
  }

  .toolbar {
    align-items: stretch;
  }

  .toolbar .el-button {
    width: 100%;
    margin-left: 0;
  }
}
</style>
