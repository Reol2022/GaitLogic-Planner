<template>
  <div class="page-stack">
    <div class="excel-section-title">每周复盘 · 训练块索引</div>
    <div class="excel-subtitle">Week 1、Week 2 和「6月最后两天」这类非标准块统一在这里维护。</div>

    <div class="toolbar">
      <div class="filter-row">
        <el-select v-model="cycleId" clearable placeholder="全部周期" style="width: 240px" @change="load">
          <el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" />
        </el-select>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增训练块</el-button>
    </div>

    <div class="panel">
      <el-table :data="blocks" v-loading="loading">
        <el-table-column prop="sort_order" label="序号" width="80" />
        <el-table-column prop="block_name" label="训练块" min-width="170" />
        <el-table-column prop="block_type" label="类型" width="110" />
        <el-table-column prop="date_range_text" label="日期范围" min-width="140" />
        <el-table-column prop="planned_distance_km" label="计划 km" width="110" />
        <el-table-column prop="phase_name" label="阶段" min-width="130" />
        <el-table-column prop="focus" label="重点" min-width="220" show-overflow-tooltip />
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑训练块' : '新增训练块'" width="760px">
      <el-form label-width="110px">
        <div class="form-grid">
          <el-form-item label="周期">
            <el-select v-model="form.cycle_id" filterable style="width: 100%">
              <el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="块名称">
            <el-input v-model="form.block_name" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="form.block_type" style="width: 100%">
              <el-option v-for="item in blockTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="form.sort_order" :min="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="周序号">
            <el-input-number v-model="form.week_index" :min="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="日期范围文本">
            <el-input v-model="form.date_range_text" />
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="计划 km">
            <el-input-number v-model="form.planned_distance_km" :precision="1" :min="0" style="width: 100%" />
          </el-form-item>
          <el-form-item label="阶段">
            <el-input v-model="form.phase_name" />
          </el-form-item>
          <el-form-item label="目标" class="full">
            <el-input v-model="form.target_text" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="重点" class="full">
            <el-input v-model="form.focus" type="textarea" :rows="2" />
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

import { listTrainingCycles } from "@/api/trainingCycles";
import {
  createTrainingBlock,
  deleteTrainingBlock,
  listTrainingBlocks,
  updateTrainingBlock,
} from "@/api/trainingBlocks";
import type { TrainingBlock, TrainingBlockPayload, TrainingCycle } from "@/types/models";
import { blockTypeOptions } from "@/types/options";

const cycles = ref<TrainingCycle[]>([]);
const blocks = ref<TrainingBlock[]>([]);
const cycleId = ref<number | null>(null);
const loading = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number | null>(null);

const emptyForm: TrainingBlockPayload = {
  cycle_id: 0,
  block_name: "",
  block_type: "week",
  week_index: null,
  sort_order: 1,
  date_range_text: null,
  target_text: null,
  target_distance_min_km: null,
  target_distance_max_km: null,
  planned_distance_km: null,
  start_date: null,
  end_date: null,
  phase_name: null,
  focus: null,
};
const form = reactive<TrainingBlockPayload>({ ...emptyForm });

async function loadCycles() {
  cycles.value = await listTrainingCycles();
}

async function load() {
  loading.value = true;
  try {
    blocks.value = await listTrainingBlocks(cycleId.value);
  } finally {
    loading.value = false;
  }
}

function openDialog(row?: TrainingBlock) {
  Object.assign(form, emptyForm);
  form.cycle_id = cycleId.value || cycles.value[0]?.id || 0;
  editingId.value = row?.id ?? null;
  if (row) Object.assign(form, row);
  dialogVisible.value = true;
}

async function submit() {
  if (editingId.value) await updateTrainingBlock(editingId.value, form);
  else await createTrainingBlock(form);
  dialogVisible.value = false;
  await load();
}

async function remove(row: TrainingBlock) {
  await ElMessageBox.confirm(`确认删除训练块「${row.block_name}」？`, "删除确认", {
    type: "warning",
  });
  await deleteTrainingBlock(row.id);
  await load();
}

onMounted(async () => {
  await loadCycles();
  await load();
});
</script>
