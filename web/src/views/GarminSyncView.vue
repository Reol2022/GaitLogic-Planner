<template>
  <div class="garmin-sync page-stack">
    <PageHeader title="Garmin 同步" subtitle="连接账号后，手动拉取跑步活动并写入训练日志。" />

    <section class="status-band">
      <div>
        <span class="eyebrow">连接状态</span>
        <strong>{{ statusLabel }}</strong>
        <small>{{ statusText }}</small>
      </div>
      <div class="actions">
        <el-button v-if="status.connected" plain :icon="Close" :loading="disconnecting" @click="handleDisconnect">断开</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="handleRefresh">刷新任务</el-button>
      </div>
    </section>

    <section v-if="!status.connected" class="panel connect-panel">
      <el-form :model="connectForm" label-position="top" @submit.prevent>
        <el-row :gutter="12">
          <el-col :xs="24" :md="9">
            <el-form-item label="Garmin 账号">
              <el-input v-model="connectForm.username" autocomplete="username" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="9">
            <el-form-item label="密码">
              <el-input v-model="connectForm.password" type="password" autocomplete="current-password" show-password />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="6">
            <el-form-item label="区域">
              <el-select v-model="connectForm.region">
                <el-option label="中国" value="cn" />
                <el-option label="全球" value="global" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <div class="form-footer">
          <el-alert
            v-if="connectError"
            :title="connectError"
            type="warning"
            show-icon
            :closable="false"
          />
          <el-button type="primary" :icon="Connection" :loading="connecting" @click="handleConnect">连接 Garmin</el-button>
        </div>
      </el-form>
    </section>

    <section v-else class="panel sync-panel">
      <div class="sync-settings">
        <span>同步后自动导入训练计划</span>
        <el-switch
          v-model="status.auto_import_enabled"
          :loading="savingSettings"
          active-text="开启"
          inactive-text="关闭"
          @change="handleAutoImportChange"
        />
      </div>
      <div class="sync-options">
        <el-segmented v-model="syncForm.sync_mode" :options="syncOptions" />
        <template v-if="syncForm.sync_mode === 'custom_range'">
          <el-date-picker v-model="customRange" type="datetimerange" start-placeholder="开始" end-placeholder="结束" />
        </template>
        <el-button type="primary" :icon="Upload" :loading="syncing" @click="handleSync">开始同步</el-button>
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>同步任务</h2>
      </div>
      <el-table :data="jobs" size="small" empty-text="暂无同步任务">
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column label="模式" min-width="120">
          <template #default="{ row }">{{ formatStatusLabel(row.sync_mode) }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="120">
          <template #default="{ row }">
            <el-tag :type="jobTagType(row.status)">{{ formatStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="结果" min-width="220">
          <template #default="{ row }">
            新增 {{ row.created_count }} / 更新 {{ row.updated_count }} / 待处理 {{ row.needs_review_count }} / 失败 {{ row.failed_count }}
          </template>
        </el-table-column>
        <el-table-column label="训练状态" min-width="250">
          <template #default="{ row }">
            <RunnerStateSnapshotSyncStatus :result="row.runner_state_snapshot" />
          </template>
        </el-table-column>
        <el-table-column prop="safe_error_message" label="错误" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" min-width="90" class-name="action-column">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'failed' || row.status === 'partially_succeeded'"
              size="small"
              text
              @click="retryJob(row.id)"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>已同步活动</h2>
      </div>
      <el-table :data="activities" size="small" empty-text="暂无活动">
        <el-table-column prop="activity_date" label="日期" width="112" />
        <el-table-column prop="activity_name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="距离" width="100">
          <template #default="{ row }">{{ formatDistance(row.distance_m) }}</template>
        </el-table-column>
        <el-table-column label="时长" width="100">
          <template #default="{ row }">{{ formatDuration(row.duration_seconds) }}</template>
        </el-table-column>
        <el-table-column label="配速" width="100">
          <template #default="{ row }">{{ formatPace(row.average_pace_seconds_per_km) }}</template>
        </el-table-column>
        <el-table-column prop="average_heart_rate_bpm" label="均心率" width="90" />
        <el-table-column label="训练日志" width="96">
          <template #default="{ row }">{{ row.workout_log_id || "-" }}</template>
        </el-table-column>
        <el-table-column label="关联计划" width="96">
          <template #default="{ row }">{{ row.planned_workout_id || "-" }}</template>
        </el-table-column>
        <el-table-column label="处理状态" width="118">
          <template #default="{ row }">
            <el-tag :type="activityTagType(row.processing_status)">{{ formatStatusLabel(row.processing_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="解析状态" width="118">
          <template #default="{ row }">{{ formatStatusLabel(row.resolution_status) }}</template>
        </el-table-column>
        <el-table-column label="写入状态" min-width="130">
          <template #default="{ row }">{{ formatStatusLabel(row.apply_status) }}</template>
        </el-table-column>
        <el-table-column label="复合训练" width="96">
          <template #default="{ row }">{{ row.composite_session_key ? "是" : "否" }}</template>
        </el-table-column>
        <el-table-column label="待补 RPE" width="98">
          <template #default="{ row }">{{ row.workout_log_id && row.processing_status !== "ignored" ? "待确认" : "-" }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="240" class-name="action-column">
          <template #default="{ row }">
            <el-button v-if="row.planned_workout_id" size="small" text @click="goWorkoutLog(row.planned_workout_id)">日志</el-button>
            <el-button v-if="row.planned_workout_id" size="small" text @click="goPlans">计划</el-button>
            <el-button v-if="row.processing_status === 'needs_review'" size="small" @click="markUnplanned(row.id)">计划外</el-button>
            <el-button v-if="row.processing_status !== 'ignored'" size="small" text @click="ignoreActivity(row.id)">忽略</el-button>
            <el-button size="small" text @click="reprocessActivity(row.id)">重新处理</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Close, Connection, Refresh, Upload } from "@element-plus/icons-vue";
import {
  connectGarmin,
  disconnectGarmin,
  getGarminStatus,
  listGarminActivities,
  listGarminSyncJobs,
  reconcileGarminActivities,
  resolveGarminActivity,
  retryGarminSyncJob,
  startGarminSync,
  updateGarminSyncSettings,
} from "@/api/garminSync";
import { getRequestErrorMessage } from "@/api/request";
import RunnerStateSnapshotSyncStatus from "@/components/runner-state/RunnerStateSnapshotSyncStatus.vue";
import type { ExternalActivityRead, ExternalSyncJobRead, GarminConnectionStatus, GarminSyncPayload } from "@/types/models";
import {
  hasActiveSyncJobs,
  hasProcessingRunnerStateReceipt,
  shouldContinueGarminPolling,
} from "@/utils/garminSyncStatus";
import { statusLabel as formatStatusLabel } from "@/utils/statusLabels";

const emptyStatus: GarminConnectionStatus = { connected: false, status: "disconnected", provider: "garmin", auto_import_enabled: true };
const router = useRouter();
const status = ref<GarminConnectionStatus>(emptyStatus);
const jobs = ref<ExternalSyncJobRead[]>([]);
const activities = ref<ExternalActivityRead[]>([]);
const loading = ref(false);
const connecting = ref(false);
const disconnecting = ref(false);
const syncing = ref(false);
const savingSettings = ref(false);
const connectError = ref("");
const customRange = ref<[Date, Date] | null>(null);
let pollTimer: ReturnType<typeof window.setTimeout> | null = null;
let receiptPollCount = 0;

const connectForm = reactive({
  username: "",
  password: "",
  region: "cn",
});

const syncForm = reactive<GarminSyncPayload>({
  sync_mode: "incremental",
});

const syncOptions = [
  { label: "最新", value: "incremental" },
  { label: "首次 90 天", value: "initial_backfill" },
  { label: "7 天", value: "recent_7d" },
  { label: "30 天", value: "recent_30d" },
  { label: "自定义", value: "custom_range" },
];

const statusLabel = computed(() => (status.value.connected ? "已连接" : status.value.status === "disconnected" ? "未连接" : formatStatusLabel(status.value.status)));
const statusText = computed(() => {
  if (status.value.connected) {
    return `${status.value.masked_account_identifier || "Garmin 账号"} · 最近同步 ${status.value.last_successful_sync_at || "暂无"}`;
  }
  return status.value.last_error_code ? `最近错误：${status.value.last_error_code}` : "等待连接";
});

async function loadAll(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true;
  try {
    status.value = await getGarminStatus();
    if (status.value.connected) {
      const [jobRows, activityRows] = await Promise.all([listGarminSyncJobs(), listGarminActivities()]);
      jobs.value = jobRows;
      activities.value = activityRows;
      if (hasActiveSyncJobs(jobRows)) {
        receiptPollCount = 0;
        schedulePolling();
      } else if (shouldContinueGarminPolling(jobRows, receiptPollCount)) {
        receiptPollCount += 1;
        schedulePolling();
      } else {
        if (!hasProcessingRunnerStateReceipt(jobRows)) receiptPollCount = 0;
        stopPolling();
      }
    } else {
      jobs.value = [];
      activities.value = [];
      stopPolling();
    }
  } finally {
    if (!options.silent) loading.value = false;
  }
}

async function handleRefresh() {
  await loadAll();
  ElMessage.success("同步任务已刷新");
}

async function handleConnect() {
  connectError.value = "";
  connecting.value = true;
  try {
    const response = await connectGarmin(connectForm);
    if (response.connection) status.value = response.connection;
    connectForm.password = "";
    await loadAll();
    ElMessage.success("Garmin 已连接");
  } catch (error) {
    connectError.value = getRequestErrorMessage(error);
  } finally {
    connecting.value = false;
  }
}

async function handleDisconnect() {
  disconnecting.value = true;
  try {
    status.value = await disconnectGarmin();
    jobs.value = [];
    activities.value = [];
  } finally {
    disconnecting.value = false;
  }
}

async function handleSync() {
  syncing.value = true;
  try {
    const payload: GarminSyncPayload = { sync_mode: syncForm.sync_mode };
    if (syncForm.sync_mode === "custom_range" && customRange.value) {
      payload.start = customRange.value[0].toISOString();
      payload.end = customRange.value[1].toISOString();
    }
    await startGarminSync(payload, `garmin-${Date.now()}`);
    await loadAll();
    schedulePolling();
    ElMessage.success("同步任务已加入队列");
  } finally {
    syncing.value = false;
  }
}

async function handleAutoImportChange(value: string | number | boolean) {
  savingSettings.value = true;
  try {
    status.value = await updateGarminSyncSettings({ auto_import_enabled: Boolean(value) });
    ElMessage.success(Boolean(value) ? "已开启自动导入" : "已关闭自动导入");
  } catch (error) {
    status.value.auto_import_enabled = !Boolean(value);
    throw error;
  } finally {
    savingSettings.value = false;
  }
}

async function retryJob(jobId: number) {
  await retryGarminSyncJob(jobId);
  await loadAll();
  schedulePolling();
  ElMessage.success("已重新加入同步队列");
}

async function markUnplanned(activityId: number) {
  await resolveGarminActivity(activityId, { action: "mark_unplanned" });
  await loadAll();
}

async function ignoreActivity(activityId: number) {
  await resolveGarminActivity(activityId, { action: "ignore" });
  await loadAll();
}

async function reprocessActivity(activityId: number) {
  await reconcileGarminActivities({ dry_run: false, activity_ids: [activityId] });
  await loadAll();
  ElMessage.success("活动已重新处理");
}

function goWorkoutLog(plannedWorkoutId: number) {
  router.push(`/workouts/${plannedWorkoutId}/log`);
}

function goPlans() {
  router.push("/workouts");
}

function formatDistance(value: number | string | null | undefined) {
  if (value == null) return "-";
  return `${(Number(value) / 1000).toFixed(2)} km`;
}

function formatDuration(seconds?: number | null) {
  if (!seconds) return "-";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

function formatPace(seconds?: number | null) {
  if (!seconds) return "-";
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}/km`;
}

function jobTagType(value: string) {
  if (value === "succeeded") return "success";
  if (value === "failed") return "danger";
  if (value === "partially_succeeded") return "warning";
  return "info";
}

function activityTagType(value: string) {
  if (value === "matched" || value === "unplanned") return "success";
  if (value === "needs_review") return "warning";
  if (value === "failed") return "danger";
  return "info";
}

function schedulePolling() {
  stopPolling();
  pollTimer = window.setTimeout(async () => {
    await loadAll({ silent: true });
  }, 2500);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

onMounted(loadAll);
onBeforeUnmount(stopPolling);
</script>

<style scoped>
.garmin-sync {
  gap: 14px;
}

.status-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid #d8dde3;
  border-radius: 8px;
  background: #ffffff;
}

.status-band > div:first-child {
  display: grid;
  gap: 5px;
}

.eyebrow {
  color: #667085;
  font-size: 12px;
}

.status-band strong {
  color: #172033;
  font-size: 20px;
}

.status-band small {
  color: #667085;
}

.actions,
.form-footer,
.sync-options,
.sync-settings,
.section-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.form-footer,
.sync-options,
.sync-settings,
.section-head {
  justify-content: space-between;
}

.sync-settings {
  margin-bottom: 14px;
  color: #344054;
  font-size: 14px;
}

.panel {
  padding: 16px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.section-head h2 {
  margin: 0 0 10px;
  color: #172033;
  font-size: 16px;
}

.sync-options {
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .status-band,
  .form-footer,
  .sync-options {
    align-items: stretch;
    flex-direction: column;
  }

  .actions {
    justify-content: flex-start;
  }
}
</style>
