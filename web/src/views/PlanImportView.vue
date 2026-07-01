<template>
  <div class="page-stack plan-import-page">
    <PageHeader title="课表导入" subtitle="导入外部课表前先生成草稿，确认差异和冲突后再应用到正式计划。">
      <template #actions>
        <el-button :icon="Download" :loading="downloading" @click="handleTemplateDownload">下载模板</el-button>
      </template>
    </PageHeader>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">导入设置</h2>
      </div>
      <div class="panel-body">
        <el-form label-position="top" class="settings-grid">
          <el-form-item label="合并策略">
            <el-select v-model="mergeStrategy">
              <el-option label="替换导入日期范围内的未来未完成计划" value="replace_uncompleted_in_range" />
              <el-option label="从生效日起替换未来未完成计划" value="replace_uncompleted_from_date" />
              <el-option label="追加到现有最后计划之后" value="append_after_last_planned" />
              <el-option label="仅填补空白日期" value="fill_empty_only" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期衔接">
            <el-select v-model="anchorStrategy">
              <el-option label="最后完成训练之后" value="after_last_completed" />
              <el-option label="指定生效日期" value="explicit_date" />
            </el-select>
          </el-form-item>
          <el-form-item label="生效日期">
            <el-date-picker
              v-model="effectiveDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="仅指定日期时必填"
              :disabled="anchorStrategy !== 'explicit_date'"
            />
          </el-form-item>
        </el-form>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">创建导入草稿</h2>
      </div>
      <div class="panel-body">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="粘贴 JSON" name="json">
            <el-input
              v-model="jsonText"
              type="textarea"
              :rows="12"
              placeholder='可以粘贴 {"workouts":[...]} 或直接粘贴数组。每条训练需包含 planned_date 或 day_offset。'
            />
            <div class="action-row">
              <el-button type="primary" :icon="DocumentAdd" :loading="submitting" @click="submitJson">
                生成草稿
              </el-button>
            </div>
          </el-tab-pane>
          <el-tab-pane label="上传文件" name="file">
            <el-upload
              drag
              accept=".json,.xlsx,.csv,.txt,.md"
              :auto-upload="false"
              :limit="1"
              :file-list="fileList"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖拽文件到这里，或点击选择文件</div>
              <template #tip>
                <div class="el-upload__tip">支持 .json、.xlsx、.csv、.txt、.md；.xls 暂不支持。</div>
              </template>
            </el-upload>
            <div class="action-row">
              <el-button type="primary" :icon="Upload" :loading="submitting" :disabled="!selectedFile" @click="submitFile">
                上传并生成草稿
              </el-button>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </section>

    <section v-if="draft" class="panel">
      <div class="panel-header">
        <h2 class="panel-title">差异预览</h2>
        <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
      </div>
      <div class="panel-body">
        <div v-if="draft.diff_summary" class="metric-grid import-metrics">
          <div v-for="metric in diffMetrics" :key="metric.label" class="metric-card">
            <div class="metric-label">{{ metric.label }}</div>
            <div class="metric-value">{{ metric.value }}</div>
          </div>
        </div>

        <el-alert
          v-if="draft.status === 'conflict'"
          title="当前草稿存在冲突，需要修正后重新校验，不能直接应用。"
          type="warning"
          show-icon
          :closable="false"
        />
        <el-alert
          v-else-if="draft.status === 'ready'"
          title="草稿已通过校验。应用时不会修改已经完成或已有训练日志的记录。"
          type="success"
          show-icon
          :closable="false"
        />

        <div v-if="allConflicts.length" class="issue-list">
          <h3>冲突</h3>
          <div v-for="(issue, index) in allConflicts" :key="`conflict-${index}`" class="issue-item">
            <strong>{{ issue.code }}</strong>
            <span>{{ issue.message }}</span>
          </div>
        </div>

        <div v-if="allWarnings.length" class="issue-list">
          <h3>警告</h3>
          <div v-for="(issue, index) in allWarnings" :key="`warning-${index}`" class="issue-item">
            <strong>{{ issue.code }}</strong>
            <span>{{ issue.message }}</span>
          </div>
        </div>

        <div class="draft-actions">
          <el-button :loading="validating" @click="refreshDraft">重新校验</el-button>
          <el-popconfirm
            width="320"
            title="本次操作将替换未来未完成计划，不会修改已经完成或已有训练日志的记录。确认应用？"
            confirm-button-text="确认应用"
            cancel-button-text="再检查一下"
            @confirm="handleApply"
          >
            <template #reference>
              <el-button type="primary" :loading="applying" :disabled="draft.status !== 'ready'">确认应用</el-button>
            </template>
          </el-popconfirm>
          <el-button :loading="cancelling" @click="handleCancel">取消草稿</el-button>
        </div>
      </div>
    </section>

    <section v-if="draft?.items?.length" class="panel">
      <div class="panel-header">
        <h2 class="panel-title">草稿条目</h2>
      </div>
      <div class="panel-body import-item-list">
        <article v-for="item in draft.items" :key="item.id" class="import-item-card">
          <div class="item-main">
            <div class="item-title">
              <span>{{ item.planned_date || item.normalized_item?.planned_date || "未定日期" }}</span>
              <el-tag size="small" effect="plain">第 {{ item.session_index || item.normalized_item?.session_index || 1 }} 练</el-tag>
              <el-tag size="small" :type="operationTagType(item.operation)">{{ operationLabel(item.operation) }}</el-tag>
            </div>
            <p>{{ item.normalized_item?.content || "空训练内容" }}</p>
            <small>{{ item.normalized_item?.workout_type || "unknown" }} · {{ item.normalized_item?.target_pace || "无配速" }}</small>
          </div>
          <el-button size="small" @click="openEditor(item)">编辑</el-button>
        </article>
      </div>
    </section>

    <el-drawer v-model="editorVisible" title="编辑草稿条目" size="min(560px, 92vw)">
      <el-input v-model="editingJson" type="textarea" :rows="18" />
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingItem" @click="saveItem">保存并重新校验</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { UploadFile, UploadUserFile } from "element-plus";
import { ElMessage } from "element-plus";
import { DocumentAdd, Download, Upload, UploadFilled } from "@element-plus/icons-vue";
import {
  applyPlanImport,
  cancelPlanImport,
  createStructuredPlanImport,
  downloadPlanImportTemplate,
  PLAN_IMPORT_TEMPLATE_FILENAME,
  updatePlanImportItem,
  uploadPlanImportFile,
  validatePlanImport,
} from "@/api/planImports";
import type {
  PlanImportAnchorStrategy,
  PlanImportDraftRead,
  PlanImportIssue,
  PlanImportItemRead,
  PlanImportMergeStrategy,
  PlanImportStructuredPayload,
  PlanImportWorkoutItem,
} from "@/types/models";

const activeTab = ref("json");
const mergeStrategy = ref<PlanImportMergeStrategy>("replace_uncompleted_in_range");
const anchorStrategy = ref<PlanImportAnchorStrategy>("after_last_completed");
const effectiveDate = ref<string | null>(null);
const jsonText = ref("");
const fileList = ref<UploadUserFile[]>([]);
const selectedFile = ref<File | null>(null);
const draft = ref<PlanImportDraftRead | null>(null);
const downloading = ref(false);
const submitting = ref(false);
const validating = ref(false);
const applying = ref(false);
const cancelling = ref(false);
const editorVisible = ref(false);
const savingItem = ref(false);
const editingItem = ref<PlanImportItemRead | null>(null);
const editingJson = ref("");

const statusLabel = computed(() => {
  const status = draft.value?.status;
  const labels: Record<string, string> = {
    uploaded: "已上传",
    parsed: "已解析",
    validation_failed: "校验失败",
    ready: "可应用",
    conflict: "存在冲突",
    applied: "已应用",
    cancelled: "已取消",
    expired: "已过期",
  };
  return status ? labels[status] || status : "";
});

const statusTagType = computed(() => {
  if (!draft.value) return "info";
  if (draft.value.status === "ready") return "success";
  if (draft.value.status === "conflict" || draft.value.status === "validation_failed") return "warning";
  if (draft.value.status === "applied") return "info";
  return "info";
});

const diffMetrics = computed(() => {
  const summary = draft.value?.diff_summary;
  if (!summary) return [];
  return [
    { label: "保留", value: summary.preserved_count },
    { label: "新增", value: summary.created_count },
    { label: "修改", value: summary.updated_count },
    { label: "删除", value: summary.removed_count },
    { label: "保护", value: summary.protected_count },
    { label: "冲突", value: summary.conflict_count },
    { label: "警告", value: summary.warning_count },
  ];
});

const allConflicts = computed(() => collectIssues("conflicts"));
const allWarnings = computed(() => collectIssues("warnings"));

function collectIssues(key: "conflicts" | "warnings"): PlanImportIssue[] {
  const result = [...(draft.value?.[key] || [])];
  for (const item of draft.value?.items || []) {
    result.push(...(item[key] || []));
  }
  return result;
}

function basePayload(): Omit<PlanImportStructuredPayload, "workouts"> {
  return {
    source: activeTab.value,
    client_request_id: buildRequestId(),
    anchor_strategy: anchorStrategy.value,
    effective_date: anchorStrategy.value === "explicit_date" ? effectiveDate.value : null,
    merge_strategy: mergeStrategy.value,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
  };
}

function buildRequestId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `plan-import-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parseJsonWorkouts(): PlanImportWorkoutItem[] {
  const parsed = JSON.parse(jsonText.value);
  if (Array.isArray(parsed)) return parsed;
  if (Array.isArray(parsed.workouts)) return parsed.workouts;
  throw new Error("JSON 必须是 workouts 数组，或包含 workouts 字段。");
}

async function submitJson() {
  if (anchorStrategy.value === "explicit_date" && !effectiveDate.value) {
    ElMessage.error("请选择生效日期");
    return;
  }
  submitting.value = true;
  try {
    const payload: PlanImportStructuredPayload = {
      ...basePayload(),
      workouts: parseJsonWorkouts(),
    };
    draft.value = await createStructuredPlanImport(payload, payload.client_request_id || undefined);
    ElMessage.success("草稿已生成");
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof Error) ElMessage.error(error.message);
  } finally {
    submitting.value = false;
  }
}

function handleFileChange(uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  const raw = uploadFile.raw;
  if (!raw) {
    selectedFile.value = null;
    return;
  }
  const allowed = [".json", ".xlsx", ".csv", ".txt", ".md"];
  if (!allowed.some((suffix) => raw.name.toLowerCase().endsWith(suffix))) {
    ElMessage.error("仅支持 .json、.xlsx、.csv、.txt、.md 文件");
    fileList.value = [];
    selectedFile.value = null;
    return;
  }
  fileList.value = uploadFiles.slice(-1);
  selectedFile.value = raw;
}

function handleFileRemove() {
  fileList.value = [];
  selectedFile.value = null;
}

async function submitFile() {
  if (!selectedFile.value) return;
  if (anchorStrategy.value === "explicit_date" && !effectiveDate.value) {
    ElMessage.error("请选择生效日期");
    return;
  }
  submitting.value = true;
  try {
    draft.value = await uploadPlanImportFile(selectedFile.value, basePayload());
    ElMessage.success("草稿已生成");
  } finally {
    submitting.value = false;
  }
}

async function handleTemplateDownload() {
  downloading.value = true;
  try {
    const blob = await downloadPlanImportTemplate();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = PLAN_IMPORT_TEMPLATE_FILENAME;
    link.click();
    URL.revokeObjectURL(url);
  } finally {
    downloading.value = false;
  }
}

async function refreshDraft() {
  if (!draft.value) return;
  validating.value = true;
  try {
    draft.value = await validatePlanImport(draft.value.import_id);
    ElMessage.success("校验已刷新");
  } finally {
    validating.value = false;
  }
}

async function handleApply() {
  if (!draft.value) return;
  applying.value = true;
  try {
    await applyPlanImport(draft.value.import_id);
    draft.value = await validatePlanImport(draft.value.import_id);
    ElMessage.success("导入草稿已应用");
  } finally {
    applying.value = false;
  }
}

async function handleCancel() {
  if (!draft.value) return;
  cancelling.value = true;
  try {
    await cancelPlanImport(draft.value.import_id);
    draft.value.status = "cancelled";
    ElMessage.success("草稿已取消");
  } finally {
    cancelling.value = false;
  }
}

function openEditor(item: PlanImportItemRead) {
  editingItem.value = item;
  editingJson.value = JSON.stringify(item.normalized_item || {}, null, 2);
  editorVisible.value = true;
}

async function saveItem() {
  if (!draft.value || !editingItem.value) return;
  savingItem.value = true;
  try {
    const normalizedItem = JSON.parse(editingJson.value) as PlanImportWorkoutItem;
    draft.value = await updatePlanImportItem(draft.value.import_id, editingItem.value.id, normalizedItem);
    editorVisible.value = false;
    ElMessage.success("草稿条目已更新");
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof Error) ElMessage.error(error.message);
  } finally {
    savingItem.value = false;
  }
}

function operationLabel(operation?: string | null) {
  const labels: Record<string, string> = {
    create: "新增",
    update: "修改",
    remove: "删除",
    preserve: "保留",
    conflict: "冲突",
  };
  return operation ? labels[operation] || operation : "待定";
}

function operationTagType(operation?: string | null) {
  if (operation === "create") return "success";
  if (operation === "update") return "warning";
  if (operation === "remove") return "danger";
  if (operation === "conflict") return "danger";
  return "info";
}
</script>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.action-row,
.draft-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.import-metrics {
  margin-bottom: 14px;
}

.issue-list {
  margin-top: 14px;
}

.issue-list h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.issue-item {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid var(--card-border);
  color: #4b5563;
}

.issue-item strong {
  min-width: 120px;
  color: #172033;
}

.import-item-list {
  display: grid;
  gap: 10px;
}

.import-item-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #fff;
}

.item-main {
  min-width: 0;
}

.item-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: #172033;
}

.item-main p {
  margin: 8px 0 4px;
  color: #374151;
}

.item-main small {
  color: #6b7280;
}

@media (max-width: 760px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .import-item-card {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
