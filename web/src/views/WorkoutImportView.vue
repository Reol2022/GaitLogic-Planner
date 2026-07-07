<template>
  <div class="page-stack workout-import-page">
    <PageHeader title="训练记录导入" subtitle="课表导入用于添加未来训练计划；训练记录导入用于补录已经完成的训练数据。">
      <template #actions>
        <el-button :icon="Download" :loading="downloading" @click="handleTemplateDownload">下载模板</el-button>
      </template>
    </PageHeader>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">导入设置</h2>
      </div>
      <div class="panel-body settings-layout">
        <el-form label-position="top">
          <el-form-item label="合并策略">
            <el-radio-group v-model="mergeStrategy">
              <el-radio-button label="create_missing_only">仅创建缺失记录</el-radio-button>
              <el-radio-button label="fill_empty_fields">仅补充空字段</el-radio-button>
              <el-radio-button label="update_objective_fields">更新客观数据</el-radio-button>
              <el-radio-button label="manual_review">全部人工确认</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">创建训练记录草稿</h2>
      </div>
      <div class="panel-body">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="粘贴 JSON" name="json">
            <el-input
              v-model="jsonText"
              type="textarea"
              :rows="12"
              placeholder='{"activities":[{"activity_date":"2026-07-01","session_index":1,"sport_type":"running","workout_type":"E","distance_km":12.3,"duration_seconds":3012,"completion_status":"completed"}]}'
            />
            <div class="action-row">
              <el-button type="primary" :icon="DocumentAdd" :loading="submitting" @click="submitJson">生成草稿</el-button>
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
                <div class="el-upload__tip">支持 JSON、Excel、CSV、规范 TXT 与 Markdown。</div>
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
        <h2 class="panel-title">解析结果</h2>
        <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
      </div>
      <div class="panel-body">
        <div class="metric-grid import-metrics">
          <div v-for="metric in metrics" :key="metric.label" class="metric-card">
            <div class="metric-label">{{ metric.label }}</div>
            <div class="metric-value">{{ metric.value }}</div>
          </div>
        </div>

        <el-alert
          title="本次操作将补录已完成训练，并可能更新部分允许更新的客观字段。已有人工填写的主观数据不会被静默覆盖。"
          type="info"
          show-icon
          :closable="false"
        />

        <div class="draft-actions">
          <el-button :loading="validating" @click="refreshDraft">重新校验</el-button>
          <el-popconfirm
            width="360"
            title="确认应用这批训练记录草稿？"
            confirm-button-text="确认应用"
            cancel-button-text="继续检查"
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

    <section v-if="items.length" class="panel">
      <div class="panel-header">
        <h2 class="panel-title">条目预览</h2>
      </div>
      <div class="panel-body import-item-list">
        <article v-for="item in items" :key="item.id" class="import-item-card">
          <div class="item-heading">
            <div>
              <strong>{{ item.normalized_data_json?.title || item.normalized_data_json?.content || "训练记录" }}</strong>
              <span>{{ item.activity_date }} {{ item.start_time || "" }}</span>
            </div>
            <el-tag size="small" :type="actionTagType(item.user_action || item.suggested_action)">
              {{ actionLabel(item.user_action || item.suggested_action) }}
            </el-tag>
          </div>
          <div class="item-facts">
            <span>{{ item.normalized_data_json?.workout_type || "类型未填" }}</span>
            <span>{{ item.normalized_data_json?.distance_km ?? "无距离" }} km</span>
            <span>{{ item.normalized_data_json?.duration_seconds ?? "无时长" }} 秒</span>
            <span>HR {{ item.normalized_data_json?.average_heart_rate_bpm ?? "-" }}</span>
            <span>RPE {{ item.normalized_data_json?.rpe ?? "待补充" }}</span>
          </div>
          <div class="item-match">
            <span>计划：{{ item.matched_plan_id || "计划外" }}</span>
            <span>日志：{{ item.matched_log_id || "未匹配" }}</span>
            <span>置信度：{{ item.match_confidence || "-" }}</span>
          </div>
          <div v-if="item.field_diff_json?.length" class="diff-list">
            <div v-for="(diff, index) in item.field_diff_json" :key="index" class="diff-line">
              <strong>{{ diff.field }}</strong>
              <span>{{ diff.existing_value ?? "空" }} → {{ diff.incoming_value ?? "空" }}</span>
            </div>
          </div>
          <div v-if="item.validation_errors_json?.length || item.warnings_json?.length" class="issue-strip">
            <el-tag v-for="issue in [...(item.validation_errors_json || []), ...(item.warnings_json || [])]" :key="`${item.id}-${issue.code}`" size="small" type="warning">
              {{ issue.message }}
            </el-tag>
          </div>
          <div class="item-actions">
            <el-select v-model="item.user_action" size="small" placeholder="处理方式" @change="(value) => updateItemAction(item.id, String(value))">
              <el-option label="按推荐处理" :value="null" />
              <el-option label="创建日志" value="create_log" />
              <el-option label="创建计划外日志" value="create_unplanned_log" />
              <el-option label="仅补充空字段" value="fill_empty_fields" />
              <el-option label="更新客观数据" value="update_objective_fields" />
              <el-option label="保留已有日志" value="keep_existing" />
              <el-option label="跳过" value="skip" />
              <el-option label="人工复核" value="manual_review" />
            </el-select>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { UploadFile, UploadUserFile } from "element-plus";
import { ElMessage } from "element-plus";
import { DocumentAdd, Download, Upload, UploadFilled } from "@element-plus/icons-vue";
import {
  applyWorkoutImport,
  cancelWorkoutImport,
  createStructuredWorkoutImport,
  downloadWorkoutImportTemplate,
  updateWorkoutImportItem,
  uploadWorkoutImportFile,
  validateWorkoutImport,
} from "@/api/workoutImports";
import type {
  NormalizedWorkoutActivity,
  WorkoutImportAction,
  WorkoutImportCreateResponse,
  WorkoutImportItemRead,
  WorkoutImportMergeStrategy,
  WorkoutImportStructuredPayload,
} from "@/types/models";

const activeTab = ref("json");
const mergeStrategy = ref<WorkoutImportMergeStrategy>("create_missing_only");
const jsonText = ref("");
const fileList = ref<UploadUserFile[]>([]);
const selectedFile = ref<File | null>(null);
const draft = ref<WorkoutImportCreateResponse | null>(null);
const downloading = ref(false);
const submitting = ref(false);
const validating = ref(false);
const applying = ref(false);
const cancelling = ref(false);

const items = computed<WorkoutImportItemRead[]>(() => draft.value?.items || []);
const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    ready: "可应用",
    conflict: "存在冲突",
    validation_failed: "校验失败",
    applied: "已应用",
    cancelled: "已取消",
    expired: "已过期",
  };
  return labels[draft.value?.status || ""] || draft.value?.status || "";
});
const statusTagType = computed(() => {
  if (draft.value?.status === "ready") return "success";
  if (draft.value?.status === "conflict" || draft.value?.status === "validation_failed") return "warning";
  return "info";
});
const metrics = computed(() => {
  const value = draft.value;
  if (!value) return [];
  return [
    { label: "总条数", value: value.total_count },
    { label: "匹配计划", value: value.matched_plan_count },
    { label: "已有日志", value: value.matched_log_count },
    { label: "计划外", value: value.unplanned_count },
    { label: "可导入", value: value.ready_count },
    { label: "冲突", value: value.conflict_count },
    { label: "无效", value: value.invalid_count },
    { label: "跳过", value: value.skipped_count },
  ];
});

function buildRequestId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `workout-import-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parseActivities(): NormalizedWorkoutActivity[] {
  const parsed = JSON.parse(jsonText.value);
  if (Array.isArray(parsed)) return parsed;
  if (Array.isArray(parsed.activities)) return parsed.activities;
  throw new Error("JSON 必须是 activities 数组，或包含 activities 字段。");
}

async function submitJson() {
  submitting.value = true;
  try {
    const payload: WorkoutImportStructuredPayload = {
      source: "external_assistant",
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
      merge_strategy: mergeStrategy.value,
      client_request_id: buildRequestId(),
      activities: parseActivities(),
    };
    draft.value = await createStructuredWorkoutImport(payload, payload.client_request_id || undefined);
    ElMessage.success("训练记录导入草稿已生成");
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof Error) ElMessage.error(error.message);
  } finally {
    submitting.value = false;
  }
}

function handleFileChange(uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  const raw = uploadFile.raw;
  if (!raw) return;
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
  submitting.value = true;
  try {
    draft.value = await uploadWorkoutImportFile(selectedFile.value, {
      merge_strategy: mergeStrategy.value,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
      client_request_id: buildRequestId(),
    });
    ElMessage.success("训练记录导入草稿已生成");
  } finally {
    submitting.value = false;
  }
}

async function handleTemplateDownload() {
  downloading.value = true;
  try {
    const blob = await downloadWorkoutImportTemplate();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "workout-import-template.xlsx";
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
    const next = await validateWorkoutImport(draft.value.batch_id);
    draft.value = { ...next, batch_id: next.id, warnings: next.warnings_json || [], preview_summary: next.preview_summary_json || next };
    ElMessage.success("校验已刷新");
  } finally {
    validating.value = false;
  }
}

async function updateItemAction(itemId: number, action: string) {
  if (!draft.value) return;
  const next = await updateWorkoutImportItem(draft.value.batch_id, itemId, { user_action: action as WorkoutImportAction });
  draft.value = { ...next, batch_id: next.id, warnings: next.warnings_json || [], preview_summary: next.preview_summary_json || next };
}

async function handleApply() {
  if (!draft.value) return;
  applying.value = true;
  try {
    const result = await applyWorkoutImport(draft.value.batch_id);
    draft.value.status = result.status;
    ElMessage.success(`已创建 ${result.created_count} 条，更新 ${result.updated_count} 条`);
  } finally {
    applying.value = false;
  }
}

async function handleCancel() {
  if (!draft.value) return;
  cancelling.value = true;
  try {
    await cancelWorkoutImport(draft.value.batch_id);
    draft.value.status = "cancelled";
    ElMessage.success("草稿已取消");
  } finally {
    cancelling.value = false;
  }
}

function actionLabel(action?: string | null) {
  const labels: Record<string, string> = {
    create_log: "创建日志",
    create_unplanned_log: "计划外日志",
    fill_empty_fields: "补充空字段",
    update_objective_fields: "更新客观数据",
    keep_existing: "保留已有",
    skip: "跳过",
    manual_review: "人工复核",
    link_to_plan: "关联计划",
  };
  return action ? labels[action] || action : "按推荐";
}

function actionTagType(action?: string | null) {
  if (action === "create_log" || action === "create_unplanned_log") return "success";
  if (action === "fill_empty_fields" || action === "update_objective_fields") return "warning";
  if (action === "manual_review") return "danger";
  return "info";
}
</script>

<style scoped>
.settings-layout {
  display: grid;
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

.import-item-list {
  display: grid;
  gap: 10px;
}

.import-item-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
}

.item-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.item-heading div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.item-heading strong {
  color: #172033;
  font-size: 15px;
}

.item-heading span,
.item-match {
  color: #667085;
  font-size: 13px;
}

.item-facts,
.item-match,
.issue-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.item-facts span {
  padding: 5px 8px;
  border-radius: 6px;
  background: #f2f6fb;
  color: #344054;
  font-size: 13px;
}

.diff-list {
  display: grid;
  gap: 6px;
}

.diff-line {
  display: flex;
  gap: 10px;
  padding: 8px;
  border-radius: 6px;
  background: #fff7ed;
  color: #7c2d12;
  font-size: 13px;
}

.item-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 760px) {
  .item-heading {
    flex-direction: column;
  }

  .item-actions {
    justify-content: stretch;
  }

  .item-actions .el-select {
    width: 100%;
  }
}
</style>
