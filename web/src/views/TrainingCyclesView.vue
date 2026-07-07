<template>
  <div class="page-stack">
    <PageHeader title="训练周期" subtitle="管理训练周期、目标比赛和周期生命周期。" />

    <div class="toolbar">
      <div></div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增训练周期</el-button>
    </div>

    <div class="panel">
      <el-tabs v-model="activeTab" @tab-change="currentPage = 1">
        <el-tab-pane label="当前周期" name="active" />
        <el-tab-pane label="草稿周期" name="draft" />
        <el-tab-pane label="历史周期" name="completed" />
        <el-tab-pane label="归档周期" name="archived" />
      </el-tabs>

      <el-alert
        v-if="activeTab === 'active' && groupedCycles.length === 0"
        title="当前没有生效中的训练周期"
        type="warning"
        :closable="false"
        show-icon
      />

      <el-table :data="pagedCycles" v-loading="loading">
        <el-table-column prop="name" label="周期" min-width="150" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ cycleStatusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column prop="goal" label="目标" min-width="180" />
        <el-table-column prop="start_date" label="计划开始" width="120" />
        <el-table-column prop="end_date" label="计划结束" width="120" />
        <el-table-column prop="actual_start_date" label="实际开始" width="120" />
        <el-table-column prop="actual_end_date" label="实际结束" width="120" />
        <el-table-column prop="target_race_name" label="目标比赛" min-width="150" />
        <el-table-column prop="target_result" label="目标成绩" width="120" />
        <el-table-column label="操作" min-width="260" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button v-if="row.status === 'draft'" size="small" type="primary" @click="activate(row)">启用</el-button>
              <el-button v-if="row.status === 'active'" size="small" @click="complete(row)">提前结束</el-button>
              <el-button v-if="row.status === 'completed'" size="small" @click="archive(row)">归档</el-button>
              <el-button v-if="row.status === 'draft'" size="small" :icon="Edit" @click="openDialog(row)">编辑</el-button>
              <el-button v-if="row.status === 'draft'" size="small" type="danger" :icon="Delete" @click="remove(row)">删除草稿</el-button>
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
          :total="groupedCycles.length"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑训练周期' : '新增训练周期'" width="680px">
      <el-form label-width="96px">
        <div class="form-grid">
          <el-form-item label="周期名称">
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="目标">
            <el-input v-model="form.goal" />
          </el-form-item>
          <el-form-item label="计划开始">
            <el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="计划结束">
            <el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="目标比赛">
            <el-input v-model="form.target_race_name" />
          </el-form-item>
          <el-form-item label="比赛日期">
            <el-date-picker v-model="form.target_race_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="目标成绩">
            <el-time-picker
              v-model="form.target_result"
              value-format="HH:mm:ss"
              format="HH:mm:ss"
              :default-value="new Date(2000, 0, 1, 0, 0, 0)"
              placeholder="选择目标成绩"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="说明" class="full">
            <el-input v-model="form.description" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Delete, Edit, Plus } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";

import {
  activateTrainingCycle,
  archiveTrainingCycle,
  completeTrainingCycle,
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
const activeTab = ref("active");
const currentPage = ref(1);
const pageSize = ref(10);

const emptyForm: TrainingCyclePayload = {
  name: "",
  goal: null,
  start_date: null,
  end_date: null,
  target_race_name: null,
  target_race_date: null,
  target_result: "00:00:00",
  description: null,
};
const form = reactive<TrainingCyclePayload>({ ...emptyForm });

const groupedCycles = computed(() => cycles.value.filter((cycle) => cycle.status === activeTab.value));

const pagedCycles = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return groupedCycles.value.slice(start, start + pageSize.value);
});

function resetForm() {
  Object.assign(form, emptyForm);
}

async function load() {
  loading.value = true;
  try {
    cycles.value = await listTrainingCycles();
    if ((currentPage.value - 1) * pageSize.value >= groupedCycles.value.length) currentPage.value = 1;
  } finally {
    loading.value = false;
  }
}

function openDialog(row?: TrainingCycle) {
  resetForm();
  editingId.value = row?.id ?? null;
  if (row) {
    Object.assign(form, {
      name: row.name,
      goal: row.goal,
      start_date: row.start_date,
      end_date: row.end_date,
      target_race_name: row.target_race_name,
      target_race_date: row.target_race_date,
      target_result: row.target_result || "00:00:00",
      description: row.description,
    });
  }
  dialogVisible.value = true;
}

async function submit() {
  if (editingId.value) await updateTrainingCycle(editingId.value, form);
  else await createTrainingCycle(form);
  dialogVisible.value = false;
  activeTab.value = "draft";
  await load();
}

async function remove(row: TrainingCycle) {
  await ElMessageBox.confirm(`确认删除训练周期「${row.name}」？`, "删除确认", {
    type: "warning",
    confirmButtonText: "删除",
    cancelButtonText: "取消",
  });
  await deleteTrainingCycle(row.id);
  await load();
}

async function activate(row: TrainingCycle) {
  const effectiveStartDate = row.start_date || new Date().toISOString().slice(0, 10);
  await ElMessageBox.confirm(
    `确认启用「${row.name}」？新周期生效日期：${effectiveStartDate}。当前 active 周期会结束，未来未完成计划会标记为 superseded，已完成训练和日志会保留。`,
    "启用周期确认",
    {
      type: "warning",
      confirmButtonText: "启用",
      cancelButtonText: "取消",
    },
  );
  await activateTrainingCycle(row.id, effectiveStartDate);
  activeTab.value = "active";
  await load();
}

async function complete(row: TrainingCycle) {
  const today = new Date().toISOString().slice(0, 10);
  await ElMessageBox.confirm(`确认提前结束「${row.name}」？未来未完成计划会标记为 superseded。`, "提前结束确认", {
    type: "warning",
    confirmButtonText: "结束",
    cancelButtonText: "取消",
  });
  await completeTrainingCycle(row.id, today);
  activeTab.value = "completed";
  await load();
}

async function archive(row: TrainingCycle) {
  await ElMessageBox.confirm(`确认归档「${row.name}」？`, "归档确认", {
    type: "warning",
    confirmButtonText: "归档",
    cancelButtonText: "取消",
  });
  await archiveTrainingCycle(row.id);
  activeTab.value = "archived";
  await load();
}

function cycleStatusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "草稿",
    active: "当前",
    completed: "历史",
    archived: "归档",
  };
  return labels[status] || status;
}

onMounted(load);
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 18px;
}

.full {
  grid-column: 1 / -1;
}

.table-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
