<template>
  <div class="page-stack">
    <div class="toolbar">
      <el-date-picker v-model="today" value-format="YYYY-MM-DD" type="date" @change="load" />
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="panel">
      <el-table :data="workouts" v-loading="loading" empty-text="今天还没有训练计划">
        <el-table-column prop="workout_date" label="日期" width="120" />
        <el-table-column prop="weekday" label="星期" width="90" />
        <el-table-column prop="planned_content" label="今日计划" min-width="260" />
        <el-table-column prop="planned_distance_km" label="计划 km" width="110" />
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            {{ labelFor(statusOptions, row.workout_log?.status_normalized) }}
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { EditPen, Refresh } from "@element-plus/icons-vue";

import { listTodayWorkouts } from "@/api/plannedWorkouts";
import type { PlannedWorkout } from "@/types/models";
import { labelFor, statusOptions } from "@/types/options";

const router = useRouter();
const today = ref(new Date().toISOString().slice(0, 10));
const workouts = ref<PlannedWorkout[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    workouts.value = await listTodayWorkouts(today.value);
  } finally {
    loading.value = false;
  }
}

function goLog(id: number) {
  router.push(`/workouts/${id}/log`);
}

onMounted(load);
</script>

