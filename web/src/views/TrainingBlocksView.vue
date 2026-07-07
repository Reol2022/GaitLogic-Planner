<template>
  <div class="page-stack">
    <PageHeader title="训练块" subtitle="用于维护 Week 1、Week 2 和非标准训练块。" />

    <div class="toolbar">
      <div class="filter-row">
        <el-select v-model="cycleId" placeholder="当前训练周期" style="width: 240px" @change="load">
          <el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" />
        </el-select>
      </div>
      <el-button type="primary" :icon="Plus" :disabled="hasNoActiveCycle" @click="openDialog()">新增训练块</el-button>
    </div>

    <div class="panel">
      <el-table :data="pagedBlocks" v-loading="loading">
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
      <div class="table-footer">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          background
          layout="total, sizes, prev, pager, next"
          :page-sizes="[10, 20, 50]"
          :total="blocks.length"
        />
      </div>
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
          <el-form-item label="日期范围">
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
import { computed, onMounted, reactive, ref } from "vue";
import { Delete, Edit, Plus } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";

import { getActiveTrainingCycle, listTrainingCycles } from "@/api/trainingCycles";
import {
  createTrainingBlock,
  deleteTrainingBlock,
  listTrainingBlocks,
  updateTrainingBlock,
} from "@/api/trainingBlocks";
import type { TrainingBlock, TrainingBlockPayload, TrainingCycle } from "@/types/models";
import { blockTypeOptions } from "@/types/options";

const cycles = ref<TrainingCycle[]>([]);
const activeCycle = ref<TrainingCycle | null>(null);
const blocks = ref<TrainingBlock[]>([]);
const cycleId = ref<number | null>(null);
const loading = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number | null>(null);
const currentPage = ref(1);
const pageSize = ref(10);
const hasNoActiveCycle = computed(() => cycles.value.length > 0 && !activeCycle.value);

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

const pagedBlocks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return blocks.value.slice(start, start + pageSize.value);
});

async function loadCycles() {
  cycles.value = await listTrainingCycles();
  try {
    activeCycle.value = await getActiveTrainingCycle();
    cycleId.value = activeCycle.value.id;
  } catch {
    activeCycle.value = null;
    cycleId.value = null;
  }
}

async function load() {
  if (!cycleId.value) {
    blocks.value = [];
    currentPage.value = 1;
    return;
  }
  loading.value = true;
  try {
    blocks.value = await listTrainingBlocks(cycleId.value);
    currentPage.value = 1;
  } finally {
    loading.value = false;
  }
}

function openDialog(row?: TrainingBlock) {
  Object.assign(form, emptyForm);
  form.cycle_id = cycleId.value || activeCycle.value?.id || 0;
  if (!form.cycle_id) return;
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
    confirmButtonText: "删除",
    cancelButtonText: "取消",
  });
  await deleteTrainingBlock(row.id);
  await load();
}

onMounted(async () => {
  await loadCycles();
  await load();
});
</script>
