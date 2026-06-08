<template>
  <div class="page-stack">
    <div class="excel-section-title">配速规则</div>
    <div class="excel-note">铁律：该慢必须慢，该快不要怂。除了质量课，禁止随心所欲加速。</div>

    <div class="toolbar">
      <div></div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增规则</el-button>
    </div>

    <div class="panel">
      <el-table :data="pagedRules" v-loading="loading">
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column prop="code" label="编码" width="90" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="target_pace_text" label="目标配速" min-width="180" />
        <el-table-column prop="physiological_purpose" label="生理目的" min-width="260" show-overflow-tooltip />
        <el-table-column prop="note" label="备注" min-width="180" show-overflow-tooltip />
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
          :total="rules.length"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑配速规则' : '新增配速规则'" width="680px">
      <el-form label-width="96px">
        <div class="form-grid">
          <el-form-item label="编码">
            <el-input v-model="form.code" />
          </el-form-item>
          <el-form-item label="名称">
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="form.sort_order" :min="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="目标配速">
            <el-input v-model="form.target_pace_text" />
          </el-form-item>
          <el-form-item label="生理目的" class="full">
            <el-input v-model="form.physiological_purpose" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="备注" class="full">
            <el-input v-model="form.note" type="textarea" :rows="2" />
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

import { createPaceRule, deletePaceRule, listPaceRules, updatePaceRule } from "@/api/paceRules";
import type { PaceRule, PaceRulePayload } from "@/types/models";

const rules = ref<PaceRule[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number | null>(null);
const currentPage = ref(1);
const pageSize = ref(10);

const emptyForm: PaceRulePayload = {
  code: "",
  name: "",
  target_pace_text: null,
  physiological_purpose: null,
  note: null,
  sort_order: 1,
};
const form = reactive<PaceRulePayload>({ ...emptyForm });

const pagedRules = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return rules.value.slice(start, start + pageSize.value);
});

async function load() {
  loading.value = true;
  try {
    rules.value = await listPaceRules();
    if ((currentPage.value - 1) * pageSize.value >= rules.value.length) currentPage.value = 1;
  } finally {
    loading.value = false;
  }
}

function openDialog(row?: PaceRule) {
  Object.assign(form, emptyForm);
  editingId.value = row?.id ?? null;
  if (row) Object.assign(form, row);
  dialogVisible.value = true;
}

async function submit() {
  if (editingId.value) await updatePaceRule(editingId.value, form);
  else await createPaceRule(form);
  dialogVisible.value = false;
  await load();
}

async function remove(row: PaceRule) {
  await ElMessageBox.confirm(`确认删除配速规则「${row.code}」？`, "删除确认", {
    type: "warning",
    confirmButtonText: "删除",
    cancelButtonText: "取消",
  });
  await deletePaceRule(row.id);
  await load();
}

onMounted(load);
</script>
