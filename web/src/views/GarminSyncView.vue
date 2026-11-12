<template>
  <div class="garmin-sync page-stack">
    <PageHeader title="Garmin 同步" subtitle="连接账号后，手动拉取跑步活动并写入训练日志。" />
    <TrainingJourney active="record" />
    <el-alert v-if="pageError" :title="pageError" type="error" :closable="false" show-icon />
    <section v-if="latestJob" class="panel latest-sync" aria-live="polite">
      <div class="section-head"><h2>{{ ['queued', 'running'].includes(latestJob.status) ? '当前同步' : '最近一次同步' }}</h2><el-tag :type="jobTagType(latestJob.status)">{{ formatStatusLabel(latestJob.status) }}</el-tag></div>
      <p>{{ syncNextStep(latestJob.status, latestJob.error_code) }}</p>
      <p v-if="latestJob.safe_error_message" class="sync-error">{{ latestJob.safe_error_message }}</p>
      <p class="sync-meta">已读取 {{ latestJob.fetched_count }} 条 · 新增 {{ latestJob.created_count }} · 更新 {{ latestJob.updated_count }} · 待确认 {{ latestJob.needs_review_count }} · 失败 {{ latestJob.failed_count }}</p>
      <p class="sync-meta">状态更新时间：{{ latestJob.updated_at }}<span v-if="pollingMessage"> · {{pollingMessage}}</span></p>
      <div class="next-sync-actions">
        <el-button v-if="['queued', 'running'].includes(latestJob.status)" :loading="isCancellingJob(latestJob.id)" @click="cancelJob(latestJob.id)">取消本次同步</el-button>
        <el-button v-if="['failed', 'partially_succeeded'].includes(latestJob.status)" :disabled="hasActiveJob" :loading="retryingJobId === latestJob.id" @click="retryJob(latestJob.id)">重试同步</el-button>
        <el-button v-if="latestJob.needs_review_count > 0" type="primary" @click="router.push('/todos')">确认活动关联</el-button>
        <el-button v-if="['succeeded', 'partially_succeeded'].includes(latestJob.status)" @click="router.push('/today')">回到今日，补充感受</el-button>
        <el-button text @click="router.push('/dashboard')">查看记录与趋势</el-button>
      </div>
    </section>

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
      <GarminSmartSyncSettings />
      <div class="sync-settings">
        <span>将同步的实际活动写入训练日志（不会创建正式课表）</span>
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
          <div v-if="compactViewport" class="mobile-date-range"><label>开始时间<input v-model="mobileRangeStart" type="datetime-local" /></label><label>结束时间<input v-model="mobileRangeEnd" type="datetime-local" /></label></div>
          <el-date-picker v-else v-model="customRange" type="datetimerange" start-placeholder="开始" end-placeholder="结束" />
        </template>
        <el-button
          type="primary"
          :icon="Upload"
          :loading="syncing"
          :disabled="hasActiveJob"
          @click="handleSync"
        >
          {{ hasActiveJob ? "已有同步任务运行中" : "开始同步" }}
        </el-button>
      </div>
    </section>

    <details class="panel sync-history">
      <summary>同步历史与错误详情（{{ jobs.length }}）</summary>
      <div class="section-head">
        <h2>同步任务</h2>
      </div>
      <div class="mobile-record-list" aria-label="同步任务卡片">
        <MobileRecordCard v-for="job in jobs" :key="job.id" :title="`#${job.id} · ${formatStatusLabel(job.sync_mode)}`">
          <template #status><el-tag :type="jobTagType(job.status)">{{formatStatusLabel(job.status)}}</el-tag></template>
          <dl><div><dt>新增 / 更新</dt><dd>{{job.created_count}} / {{job.updated_count}}</dd></div><div><dt>待确认 / 失败</dt><dd>{{job.needs_review_count}} / {{job.failed_count}}</dd></div></dl>
          <p v-if="job.safe_error_message">{{job.safe_error_message}}</p><RunnerStateSnapshotSyncStatus :result="job.runner_state_snapshot"/>
          <template #actions><el-button v-if="['queued','running'].includes(job.status)" type="danger" plain :loading="isCancellingJob(job.id)" @click="cancelJob(job.id)">取消同步</el-button><el-button v-if="['failed','partially_succeeded'].includes(job.status)" :disabled="hasActiveJob" :loading="retryingJobId===job.id" @click="retryJob(job.id)">重试同步</el-button></template>
        </MobileRecordCard>
        <el-empty v-if="!jobs.length" description="暂无同步任务"/>
      </div>
      <el-table class="desktop-record-table" :data="jobs" size="small" empty-text="暂无同步任务">
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
        <el-table-column label="操作" min-width="150" class-name="action-column">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'queued' || row.status === 'running'"
              size="small"
              type="danger"
              text
              :loading="isCancellingJob(row.id)"
              @click="cancelJob(row.id)"
            >
              取消
            </el-button>
            <el-button
              v-if="row.status === 'failed' || row.status === 'partially_succeeded'"
              :disabled="hasActiveJob"
              :loading="retryingJobId === row.id"
              size="small"
              text
              @click="retryJob(row.id)"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </details>

    <section class="panel">
      <div class="section-head">
        <h2>已同步活动 · 确认后补充感受</h2>
      </div>
      <div class="mobile-record-list" aria-label="设备活动卡片">
        <MobileRecordCard v-for="activity in activities" :key="activity.id" :title="`${activity.activity_date} · ${activity.activity_name || '跑步活动'}`">
          <template #status><el-tag :type="activityTagType(activity.processing_status)">{{formatStatusLabel(activity.processing_status)}}</el-tag></template>
          <dl><div><dt>距离</dt><dd>{{formatDistance(activity.distance_m)}}</dd></div><div><dt>时长</dt><dd>{{formatDuration(activity.duration_seconds)}}</dd></div><div><dt>配速</dt><dd>{{formatPace(activity.average_pace_seconds_per_km)}}</dd></div><div><dt>平均心率</dt><dd>{{activity.average_heart_rate_bpm ?? '暂无'}}</dd></div></dl>
          <p>{{activity.planned_workout_id ? '已关联计划' : '尚未关联计划'}} · 日志 {{activity.workout_log_id ?? '未写入'}}</p>
          <details><summary>查看处理详情</summary><p>解析：{{formatStatusLabel(activity.resolution_status)}} · 写入：{{formatStatusLabel(activity.apply_status)}}</p><p>复合训练：{{activity.composite_session_key?'是':'否'}}</p></details>
          <template #actions><el-button v-if="activity.planned_workout_id" @click="goWorkoutLog(activity.planned_workout_id)">填写日志</el-button><el-button v-if="activity.processing_status==='needs_review'" @click="markUnplanned(activity.id)">记为计划外</el-button><el-button v-if="activity.processing_status!=='ignored'" @click="ignoreActivity(activity.id)">忽略活动</el-button><el-button @click="reprocessActivity(activity.id)">重新处理</el-button></template>
        </MobileRecordCard><el-empty v-if="!activities.length" description="暂无活动"/>
      </div>
      <el-table class="desktop-record-table" :data="activities" size="small" empty-text="暂无活动">
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
          <template #default="{ row }">{{ row.workout_log_id && row.processing_status !== "ignored" ? "请查看日志" : "-" }}</template>
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
import { computed, onActivated, onDeactivated, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Close, Connection, Refresh, Upload } from "@element-plus/icons-vue";
import {
  cancelGarminSyncJob,
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
import MobileRecordCard from "@/components/common/MobileRecordCard.vue";
import GarminSmartSyncSettings from '@/components/common/GarminSmartSyncSettings.vue';
import TrainingJourney from "@/components/common/TrainingJourney.vue";
import { syncNextStep } from "@/utils/coreExperience";
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
const pageError = ref('');
const pollingMessage = ref('');
const retryingJobId = ref<number | null>(null);
const latestJob = computed(() => [...jobs.value].sort((a, b) => b.id - a.id)[0]);
let pageActive = false;
const customRange = ref<[Date, Date] | null>(null);
const compactViewport=ref(window.innerWidth<=768),mobileRangeStart=ref(''),mobileRangeEnd=ref('');
function resizeSyncViewport(){compactViewport.value=window.innerWidth<=768;}
function dateTimeInputValue(date:Date){return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}T${String(date.getHours()).padStart(2,'0')}:${String(date.getMinutes()).padStart(2,'0')}`;}
watch(customRange,range=>{if(range){mobileRangeStart.value=dateTimeInputValue(range[0]);mobileRangeEnd.value=dateTimeInputValue(range[1]);}});
watch([mobileRangeStart,mobileRangeEnd],([start,end])=>{
  const a=new Date(start),b=new Date(end);
  if(!start || !end || !Number.isFinite(a.getTime()) || !Number.isFinite(b.getTime())){customRange.value=null;return;}
  if(customRange.value?.[0].getTime()!==a.getTime() || customRange.value?.[1].getTime()!==b.getTime())customRange.value=[a,b];
});
onMounted(()=>window.addEventListener('resize',resizeSyncViewport));
onBeforeUnmount(()=>window.removeEventListener('resize',resizeSyncViewport));
let pollTimer: ReturnType<typeof window.setTimeout> | null = null;
let receiptPollCount = 0;
let activeJobPollCount = 0;
let pollGeneration = 0;
const cancelingJobIds = ref<Set<number>>(new Set());
const GARMIN_JOB_POLL_INTERVAL_MS = 8000;
const MAX_ACTIVE_JOB_POLLS = 30;

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
const hasActiveJob = computed(() => hasActiveSyncJobs(jobs.value));

async function loadAll(options: { silent?: boolean } = {}) {
  const generation = pollGeneration;
  pageError.value = '';
  pollingMessage.value = '';
  if (!options.silent) loading.value = true;
  try {
    status.value = await getGarminStatus();
    if (status.value.connected) {
      const [jobRows, activityRows] = await Promise.all([listGarminSyncJobs(), listGarminActivities()]);
      if (!pageActive || generation !== pollGeneration) return;
      jobs.value = jobRows;
      activities.value = activityRows;
      if (hasActiveSyncJobs(jobRows)) {
        receiptPollCount = 0;
        activeJobPollCount = 0;
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
  } catch (error) {
    pageError.value = getRequestErrorMessage(error);
    stopPolling();
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
  if (syncing.value || hasActiveJob.value) return;
  if (syncForm.sync_mode === 'custom_range' && !customRange.value) { ElMessage.warning('请选择完整的同步时间范围'); return; }
  if(syncForm.sync_mode==='custom_range' && customRange.value && customRange.value[0]>=customRange.value[1]){ElMessage.warning('开始时间必须早于结束时间');return;}
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
  if (hasActiveJob.value || retryingJobId.value !== null) return;
  retryingJobId.value = jobId;
  try {
    await retryGarminSyncJob(jobId);
    await loadAll();
    if (hasActiveJob.value) schedulePolling();
    ElMessage.success("已重新加入同步队列");
  } finally { retryingJobId.value = null; }
}

function isCancellingJob(jobId: number) {
  return cancelingJobIds.value.has(jobId);
}

async function cancelJob(jobId: number) {
  cancelingJobIds.value = new Set(cancelingJobIds.value).add(jobId);
  try {
    const cancelledJob = await cancelGarminSyncJob(jobId);
    jobs.value = jobs.value.map((job) => job.id === jobId ? cancelledJob : job);
    activeJobPollCount = 0;
    receiptPollCount = 0;
    stopPolling();
    ElMessage.success("同步任务已取消");
  } finally {
    const next = new Set(cancelingJobIds.value);
    next.delete(jobId);
    cancelingJobIds.value = next;
  }
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
  if (!pageActive) return;
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  const generation = pollGeneration;
  pollTimer = window.setTimeout(async () => {
    pollTimer = null;
    await pollSyncJobs(generation);
  }, GARMIN_JOB_POLL_INTERVAL_MS);
}

async function pollSyncJobs(generation: number) {
  try {
    const jobRows = await listGarminSyncJobs();
    if (generation !== pollGeneration) return;
    jobs.value = jobRows;
    if (hasActiveSyncJobs(jobRows)) {
      receiptPollCount = 0;
      activeJobPollCount += 1;
      if (activeJobPollCount < MAX_ACTIVE_JOB_POLLS) {
        schedulePolling();
      } else {
        stopPolling();
        pollingMessage.value = '已暂停自动刷新，可手动刷新或取消任务';
        ElMessage.info("同步任务仍在后台运行，已暂停自动刷新，可手动刷新或取消任务");
      }
      return;
    }
    if (shouldContinueGarminPolling(jobRows, receiptPollCount)) {
      receiptPollCount += 1;
      schedulePolling();
      return;
    }

    receiptPollCount = 0;
    activeJobPollCount = 0;
    const [nextStatus, activityRows] = await Promise.all([
      getGarminStatus(true),
      listGarminActivities(),
    ]);
    if (generation !== pollGeneration || !pageActive) return;
    status.value = nextStatus;
    activities.value = activityRows;
  } catch {
    // Stop automatic polling on a network error. The user can refresh manually,
    // avoiding an endless request loop while the backend or Garmin is unavailable.
    stopPolling();
    pollingMessage.value = '网络异常，已停止自动刷新。请检查网络后手动刷新。';
  }
}

function stopPolling() {
  pollGeneration += 1;
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

onMounted(() => { pageActive = true; void loadAll(); });
onActivated(() => { if (!pageActive) { pageActive = true; void loadAll(); } });
onDeactivated(() => { pageActive = false; stopPolling(); });
onBeforeUnmount(stopPolling);
</script>

<style scoped>
.mobile-date-range{display:grid;gap:12px;width:100%;min-width:0}.mobile-date-range label{display:grid;gap:8px;font-size:13px;color:var(--muted);min-width:0}.mobile-date-range input{min-height:44px;min-width:0;width:100%;max-width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:16px;background:var(--surface);color:var(--text);box-sizing:border-box}
.latest-sync p{line-height:1.7}.sync-meta{font-size:13px;color:var(--muted);overflow-wrap:anywhere}.sync-error{color:var(--danger)}.sync-history>summary{cursor:pointer;font-weight:600;padding:4px 0 14px}.next-sync-actions{display:flex;gap:10px;flex-wrap:wrap}.next-sync-actions :deep(.el-button){margin-left:0}@media(max-width:600px){.next-sync-actions{display:grid}.next-sync-actions :deep(.el-button){width:100%}}
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
  .sync-settings{align-items:flex-start;flex-direction:column;gap:12px}.sync-options :deep(.el-segmented){width:100%;max-width:100%;overflow-x:auto}.sync-options :deep(.el-segmented__group){min-width:max-content}.sync-options :deep(.el-segmented__item){min-height:44px}.sync-options :deep(.el-date-editor){width:100%;max-width:100%}.sync-options>.el-button,.actions>.el-button{min-height:44px}.actions{display:flex;flex-wrap:wrap}.actions>.el-button{flex:1;margin:0}.sync-panel,.sync-history{overflow:visible!important}
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
