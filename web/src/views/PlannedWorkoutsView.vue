<template>
  <div class="page-stack">
    <div class="toolbar">
      <div class="filter-row">
        <el-select
          v-model="filterCycleId"
          clearable
          placeholder="训练周期"
          style="width: 220px"
          @change="loadFilterBlocks"
        >
          <el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" />
        </el-select>
        <el-select v-model="filterBlockId" clearable placeholder="训练块" style="width: 220px">
          <el-option v-for="block in filterBlocks" :key="block.id" :label="block.block_name" :value="block.id" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
        />
        <el-select v-model="mainType" clearable placeholder="训练类型" style="width: 170px">
          <el-option v-for="item in mainTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button :icon="Search" @click="load">查询</el-button>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增计划</el-button>
    </div>

    <div class="panel">
      <el-table :data="workouts" v-loading="loading">
        <el-table-column prop="workout_date" label="日期" width="120" />
        <el-table-column prop="weekday" label="星期" width="90" />
        <el-table-column prop="phase_name" label="阶段" min-width="120" />
        <el-table-column prop="planned_content" label="计划内容" min-width="260" show-overflow-tooltip />
        <el-table-column prop="planned_distance_km" label="计划 km" width="110" />
        <el-table-column label="主类型" width="130">
          <template #default="{ row }">
            <el-tag>{{ labelFor(mainTypeOptions, row.main_type_normalized) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="完成状态" width="130">
          <template #default="{ row }">
            {{ labelFor(statusOptions, row.workout_log?.status_normalized) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" :icon="Edit" @click="openDialog(row)">编辑计划</el-button>
              <el-button size="small" type="primary" :icon="Document" @click="goLog(row.id)">填写日志</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="remove(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑训练计划' : '新增训练计划'" width="780px">
      <el-form label-width="108px">
        <div class="form-grid">
          <el-form-item label="训练周期">
            <el-select v-model="form.cycle_id" filterable style="width: 100%" @change="loadBlocks">
              <el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="训练块">
            <el-select v-model="form.block_id" filterable style="width: 100%">
              <el-option v-for="block in blocks" :key="block.id" :label="block.block_name" :value="block.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker v-model="form.workout_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="星期">
            <el-input v-model="form.weekday" />
          </el-form-item>
          <el-form-item label="月份">
            <el-input v-model="form.month_text" />
          </el-form-item>
          <el-form-item label="阶段">
            <el-input v-model="form.phase_name" />
          </el-form-item>
          <el-form-item label="计划 km">
            <el-input-number v-model="form.planned_distance_km" :precision="1" :min="0" style="width: 100%" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="form.sort_order" :min="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="主类型原文">
            <el-input v-model="form.main_type_raw" />
          </el-form-item>
          <el-form-item label="主类型">
            <el-select v-model="form.main_type_normalized" style="width: 100%">
              <el-option v-for="item in mainTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="计划内容" class="full">
            <el-input v-model="form.planned_content" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="重点说明" class="full">
            <el-input v-model="form.focus_note" type="textarea" :rows="2" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { Delete, Document, Edit, Plus, Search } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";

import {
  createPlannedWorkout,
  deletePlannedWorkout,
  listPlannedWorkouts,
  updatePlannedWorkout,
} from "@/api/plannedWorkouts";
import { listTrainingBlocks } from "@/api/trainingBlocks";
import { listTrainingCycles } from "@/api/trainingCycles";
import type {
  PlannedWorkout,
  PlannedWorkoutPayload,
  TrainingBlock,
  TrainingCycle,
  WorkoutMainTypeNormalized,
} from "@/types/models";
import { labelFor, mainTypeOptions, statusOptions } from "@/types/options";

const router = useRouter();
const cycles = ref<TrainingCycle[]>([]);
const blocks = ref<TrainingBlock[]>([]);
const filterBlocks = ref<TrainingBlock[]>([]);
const workouts = ref<PlannedWorkout[]>([]);
const filterCycleId = ref<number | null>(null);
const filterBlockId = ref<number | null>(null);
const dateRange = ref<[string, string] | null>(null);
const mainType = ref<WorkoutMainTypeNormalized | null>(null);
const loading = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number | null>(null);

const emptyForm: PlannedWorkoutPayload = {
  cycle_id: 0,
  block_id: 0,
  workout_date: null,
  date_text: null,
  weekday: null,
  month_text: null,
  phase_name: null,
  planned_content: "",
  focus_note: null,
  planned_distance_km: null,
  main_type_raw: null,
  main_type_normalized: "unknown",
  source_sheet: "web",
  source_row: null,
  sort_order: 1,
};
const form = reactive<PlannedWorkoutPayload>({ ...emptyForm });

async function load() {
  loading.value = true;
  try {
    workouts.value = await listPlannedWorkouts({
      cycle_id: filterCycleId.value,
      block_id: filterBlockId.value,
      start_date: dateRange.value?.[0] || null,
      end_date: dateRange.value?.[1] || null,
      main_type_normalized: mainType.value,
    });
  } finally {
    loading.value = false;
  }
}

async function loadCycles() {
  cycles.value = await listTrainingCycles();
}

async function loadBlocks() {
  blocks.value = await listTrainingBlocks(form.cycle_id || null);
  if (!blocks.value.some((block) => block.id === form.block_id)) {
    form.block_id = blocks.value[0]?.id || 0;
  }
}

async function loadFilterBlocks() {
  filterBlockId.value = null;
  filterBlocks.value = await listTrainingBlocks(filterCycleId.value);
  await load();
}

async function openDialog(row?: PlannedWorkout) {
  Object.assign(form, emptyForm);
  form.cycle_id = cycles.value[0]?.id || 0;
  editingId.value = row?.id ?? null;
  if (row) Object.assign(form, row);
  await loadBlocks();
  dialogVisible.value = true;
}

async function submit() {
  if (form.workout_date) form.date_text = form.workout_date;
  if (editingId.value) await updatePlannedWorkout(editingId.value, form);
  else await createPlannedWorkout(form);
  dialogVisible.value = false;
  await load();
}

function goLog(id: number) {
  router.push(`/workouts/${id}/log`);
}

async function remove(row: PlannedWorkout) {
  await ElMessageBox.confirm(`确认删除这条训练计划？`, "删除确认", { type: "warning" });
  await deletePlannedWorkout(row.id);
  await load();
}

onMounted(async () => {
  await loadCycles();
  filterBlocks.value = await listTrainingBlocks();
  await load();
});
</script>
