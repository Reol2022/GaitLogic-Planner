<template>
  <div class="page-stack">
    <div class="toolbar">
      <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
      <el-button type="primary" :icon="Check" @click="submit">提交日志</el-button>
    </div>

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
            <el-form-item label="原始状态">
              <el-input v-model="form.status_raw" />
            </el-form-item>
            <el-form-item label="实际 km">
              <el-input-number v-model="form.actual_distance_km" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="实际时长秒">
              <el-input-number v-model="form.actual_duration_seconds" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="均配秒/km">
              <el-input-number v-model="form.avg_pace_seconds_per_km" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="均心率">
              <el-input-number v-model="form.avg_heart_rate" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="RPE">
              <el-input-number v-model="form.rpe" :min="0" :max="10" style="width: 100%" />
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
              <el-slider v-model="painLevel" :min="0" :max="5" show-stops />
            </el-form-item>
            <el-form-item label="主课数据" class="full">
              <el-input v-model="form.main_session_data" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="一句复盘" class="full">
              <el-input v-model="form.review_note" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="明日调整" class="full">
              <el-input v-model="form.tomorrow_adjustment" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="训练警报" class="full">
              <el-input v-model="form.alert_message" type="textarea" :rows="2" />
            </el-form-item>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, Check } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { getWorkoutLog, updateWorkoutLog } from "@/api/workoutLogs";
import type { WorkoutLogPayload } from "@/types/models";
import { statusOptions } from "@/types/options";

const route = useRoute();
const router = useRouter();
const plannedWorkoutId = Number(route.params.id);
const loading = ref(false);
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

async function load() {
  loading.value = true;
  try {
    const log = await getWorkoutLog(plannedWorkoutId);
    Object.assign(form, log);
  } finally {
    loading.value = false;
  }
}

async function submit() {
  await updateWorkoutLog(plannedWorkoutId, form);
  ElMessage.success("训练日志已保存");
}

onMounted(load);
</script>

