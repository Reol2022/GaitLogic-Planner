<template>
  <div class="page-stack">
    <div class="excel-section-title">训练周期</div>
    <div class="excel-subtitle">用于管理夏训周期、目标比赛和总体目标。</div>

    <div class="toolbar">
      <div></div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增周期</el-button>
    </div>

    <div class="panel">
      <el-table :data="cycles" v-loading="loading">
        <el-table-column prop="name" label="周期" min-width="150" />
        <el-table-column prop="goal" label="目标" min-width="180" />
        <el-table-column prop="start_date" label="开始" width="120" />
        <el-table-column prop="end_date" label="结束" width="120" />
        <el-table-column prop="target_race_name" label="目标比赛" min-width="150" />
        <el-table-column prop="target_result" label="目标成绩" width="120" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" :icon="Edit" @click="openDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="remove(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑周期' : '新增周期'" width="680px">
      <el-form label-width="96px">
        <div class="form-grid">
          <el-form-item label="周期名称">
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="目标">
            <el-input v-model="form.goal" />
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="目标比赛">
            <el-input v-model="form.target_race_name" />
          </el-form-item>
          <el-form-item label="比赛日期">
            <el-date-picker v-model="form.target_race_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="目标成绩">
            <el-input v-model="form.target_result" />
          </el-form-item>
          <el-form-item label="说明" class="full">
            <el-input v-model="form.description" type="textarea" :rows="3" />
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
import { Delete, Edit, Plus } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";

import {
  createTrainingCycle,
  deleteTrainingCycle,
  listTrainingCycles,
  updateTrainingCycle,
} from "@/api/trainingCycles";
import type { TrainingCycle, TrainingCyclePayload } from "@/types/models";

const cycles = ref<TrainingCycle[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number | null>(null);

const emptyForm: TrainingCyclePayload = {
  name: "",
  goal: null,
  start_date: null,
  end_date: null,
  target_race_name: null,
  target_race_date: null,
  target_result: null,
  description: null,
};
const form = reactive<TrainingCyclePayload>({ ...emptyForm });

function resetForm() {
  Object.assign(form, emptyForm);
}

async function load() {
  loading.value = true;
  try {
    cycles.value = await listTrainingCycles();
  } finally {
    loading.value = false;
  }
}

function openDialog(row?: TrainingCycle) {
  resetForm();
  editingId.value = row?.id ?? null;
  if (row) Object.assign(form, row);
  dialogVisible.value = true;
}

async function submit() {
  if (editingId.value) await updateTrainingCycle(editingId.value, form);
  else await createTrainingCycle(form);
  dialogVisible.value = false;
  await load();
}

async function remove(row: TrainingCycle) {
  await ElMessageBox.confirm(`确认删除训练周期「${row.name}」？`, "删除确认", {
    type: "warning",
  });
  await deleteTrainingCycle(row.id);
  await load();
}

onMounted(load);
</script>
