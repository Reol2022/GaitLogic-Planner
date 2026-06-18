<template>
  <div class="page-stack ai-plan-page">
    <Transition name="generation-mask">
      <div v-if="generating" class="generation-overlay" role="status" aria-live="polite">
        <div class="generation-panel">
          <div class="generation-spinner" />
          <div class="generation-copy">
            <h3>正在生成课表草稿</h3>
            <p>{{ generationStatusText }}</p>
          </div>
          <el-progress
            :percentage="generationProgress"
            :stroke-width="10"
            :show-text="false"
            striped
          />
          <div class="generation-meta">
            <span>{{ generationProgress }}%</span>
            <span>复杂计划可能需要 1-3 分钟，请保持当前页面打开</span>
          </div>
        </div>
      </div>
    </Transition>

    <PageHeader title="AI 课表草稿生成器" subtitle="AI 生成内容仅作为训练计划草稿，请结合自身恢复、伤病和实际训练反馈调整。">
      <template #actions>
        <div class="quota-box">
          <span>{{ quota?.model_name || "deepseek-v4-flash" }}</span>
          <strong>今日剩余 {{ quota?.remaining_count ?? "-" }} 次</strong>
          <em>冷却 {{ quota?.cooldown_seconds ?? 60 }} 秒</em>
        </div>
      </template>
    </PageHeader>

    <section class="ai-grid">
      <article class="panel ai-form-card">
        <div class="panel-head">
          <div>
            <h3>跑者与目标信息</h3>
            <p>训练偏好会作为个人训练哲学传给模型，后续可升级为可保存的个人配置。</p>
          </div>
        </div>

        <el-form label-position="top" class="ai-form">
          <div class="form-row">
            <el-form-item label="近期 PB 距离">
              <el-select v-model="form.recent_pb_distance" clearable style="width: 100%">
                <el-option
                  v-for="item in distanceOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="近期 PB 成绩">
              <el-time-picker
                v-model="form.recent_pb_result"
                value-format="HH:mm:ss"
                format="HH:mm:ss"
                :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                placeholder="例如 00:16:24"
                style="width: 100%"
              />
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="当前周跑量 km">
              <el-input-number v-model="form.current_weekly_mileage_km" :min="0" :max="300" style="width: 100%" />
              <div class="form-help">请填写你最近能够稳定完成的周跑量，而不是历史最高周跑量。</div>
            </el-form-item>
            <el-form-item label="最近 4 周平均跑量 km">
              <el-input-number v-model="form.recent_4w_avg_mileage_km" :min="0" :max="300" style="width: 100%" />
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="每周可训练天数">
              <el-input-number v-model="form.available_training_days_per_week" :min="1" :max="7" style="width: 100%" />
            </el-form-item>
            <el-form-item label="目标距离">
              <el-select v-model="form.target_distance" style="width: 100%">
                <el-option v-for="item in distanceOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="目标成绩">
              <el-time-picker
                v-model="form.target_result"
                value-format="HH:mm:ss"
                format="HH:mm:ss"
                :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                placeholder="例如 01:11:30"
                style="width: 100%"
              />
              <div class="form-help">目标过于激进时，系统会保留目标，但会在计划中提示风险。</div>
            </el-form-item>
            <el-form-item label="目标赛事日期">
              <el-date-picker
                v-model="form.target_race_date"
                value-format="YYYY-MM-DD"
                :disabled-date="disableTargetRaceDate"
                style="width: 100%"
                @change="syncWeeksFromRace"
              />
            </el-form-item>
          </div>

          <el-form-item label="伤病说明">
            <el-input
              v-model="form.injury_notes"
              type="textarea"
              :rows="2"
              placeholder="例如：左小腿偶有紧张，无明显疼痛"
            />
            <div class="form-help">如有持续疼痛或明确伤病，请优先接受专业评估，AI 计划不替代医疗建议。</div>
          </el-form-item>

          <div class="form-row">
            <el-form-item label="计划开始日期">
              <el-date-picker
                v-model="form.plan_start_date"
                value-format="YYYY-MM-DD"
                :disabled-date="disablePlanStartDate"
                style="width: 100%"
                @change="syncWeeksFromRace"
              />
            </el-form-item>
            <el-form-item label="计划周数">
              <el-input-number v-model="form.plan_weeks" :min="1" :max="16" style="width: 100%" />
            </el-form-item>
          </div>

          <div class="date-summary" :class="{ invalid: Boolean(dateConstraintError) }">
            <div class="date-summary-main">
              <span class="label">计划结束日</span>
              <strong>{{ planEndDate || "未计算" }}</strong>
            </div>
            <div class="date-summary-meta">
              <span v-if="raceGapText">{{ raceGapText }}</span>
              <span v-if="dateConstraintError">{{ dateConstraintError }}</span>
              <span v-else-if="planEndDate">当前周期设置可用于生成草稿</span>
            </div>
          </div>

          <el-collapse class="advanced-collapse">
            <el-collapse-item title="高级设置" name="advanced">
              <div class="form-row">
                <el-form-item label="跑者水平">
                  <el-select v-model="form.runner_level" style="width: 100%">
                    <el-option label="初级" value="beginner" />
                    <el-option label="进阶" value="intermediate" />
                    <el-option label="严肃跑者" value="advanced" />
                  </el-select>
                </el-form-item>
                <el-form-item label="强度风格">
                  <el-select v-model="form.intensity_style" style="width: 100%">
                    <el-option label="保守" value="conservative" />
                    <el-option label="标准" value="standard" />
                    <el-option label="积极" value="aggressive" />
                  </el-select>
                </el-form-item>
              </div>
              <div class="form-row">
                <el-form-item label="目标赛事名称">
                  <el-input v-model="form.target_race_name" placeholder="眉山东坡半马" />
                </el-form-item>
                <el-form-item label="是否可以双跑">
                  <el-switch v-model="form.can_double_run" active-text="可以" inactive-text="不可以" />
                </el-form-item>
              </div>
              <el-form-item label="固定休息日">
                <el-select v-model="form.fixed_rest_days" multiple clearable style="width: 100%">
                  <el-option v-for="day in weekDays" :key="day" :label="day" :value="day" />
                </el-select>
              </el-form-item>
              <el-form-item label="训练偏好 / 训练哲学">
                <el-input
                  v-model="form.training_preferences"
                  type="textarea"
                  :rows="3"
                  placeholder="例如：偏丹尼尔斯体系；二四日关键课；不做激进双阈值；长距离希望保守推进"
                />
              </el-form-item>
              <el-form-item label="包含配速建议">
                <el-switch v-model="form.include_pace_guidance" />
              </el-form-item>
              <router-link class="preference-link" to="/ai-coach-preference">打开 AI 教练偏好配置</router-link>
            </el-collapse-item>
          </el-collapse>

          <div class="form-actions">
            <el-button
              type="primary"
              :loading="generating"
              :disabled="generating || !quota?.can_generate || Boolean(dateConstraintError)"
              @click="generate"
            >
              生成草稿
            </el-button>
            <el-button :disabled="generating" @click="loadAll">刷新额度/草稿</el-button>
          </div>
        </el-form>
      </article>

      <article class="panel draft-card">
        <div class="panel-head">
          <div>
            <h3>草稿预览</h3>
            <p>确认后再应用为正式训练计划。</p>
          </div>
        </div>
        <template v-if="currentDraft">
          <div class="draft-summary-card">
            <h4>{{ currentDraft.title }}</h4>
            <p>{{ currentDraft.summary }}</p>
            <div class="draft-metrics">
              <span><b>目标</b>{{ currentDraft.target_race_name || currentDraft.goal || "-" }} {{ currentDraft.target_result || "" }}</span>
              <span><b>周期</b>{{ currentDraft.start_date || "-" }} 至 {{ currentDraft.end_date || "-" }}</span>
              <span><b>总周期</b>{{ groupedWorkouts.length }} 周</span>
              <span><b>第一周跑量</b>{{ firstWeekDistance }} km</span>
              <span><b>关键课</b>{{ firstWeekKeyWorkoutCount }} 次/首周</span>
              <span><b>风格</b>{{ intensityStyleLabel }}</span>
            </div>
            <el-alert
              v-if="currentDraft.risk_notes?.length"
              type="warning"
              :closable="false"
              :title="currentDraft.risk_notes.join('；')"
            />
          </div>
          <div class="draft-actions">
            <el-button type="primary" :disabled="currentDraft.status !== 'draft' || applying" :loading="applying" @click="apply(currentDraft.id)">
              采用这份计划
            </el-button>
            <el-button :disabled="generating" @click="currentDraft = null">返回修改</el-button>
            <el-button :disabled="generating" @click="generate">重新生成</el-button>
            <el-button :disabled="currentDraft.status !== 'draft'" @click="reject(currentDraft.id)">拒绝草稿</el-button>
            <el-dropdown trigger="click" @command="(format) => downloadCurrentDraft(String(format))">
              <el-button :icon="Download">导出</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="item in exportOptions" :key="item.value" :command="item.value">
                    {{ item.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <p class="export-note">
            Garmin / 高驰参考 CSV 仅用于手动录入或二次转换，不会直连设备账号。
          </p>
          <div v-if="firstWeekGroup" class="week-block">
            <h4>第一周完整预览：{{ firstWeekGroup.name }}</h4>
            <el-table :data="firstWeekGroup.items" size="small">
              <el-table-column prop="workout_date" label="日期" width="110" />
              <el-table-column prop="weekday" label="星期" width="70" />
              <el-table-column prop="planned_content" label="训练内容" min-width="220" show-overflow-tooltip />
              <el-table-column prop="focus_note" label="训练目的 / 执行提示" min-width="220" show-overflow-tooltip />
              <el-table-column prop="planned_distance_km" label="km" width="70" />
              <el-table-column prop="main_type_raw" label="类型" width="80" />
              <el-table-column prop="target_pace_text" label="目标配速" width="130" show-overflow-tooltip />
            </el-table>
          </div>
          <el-collapse v-if="restWeekGroups.length">
            <el-collapse-item v-for="group in restWeekGroups" :key="group.name" :title="group.name" :name="group.name">
              <el-table :data="group.items" size="small">
                <el-table-column prop="workout_date" label="日期" width="110" />
                <el-table-column prop="planned_content" label="训练内容" min-width="260" show-overflow-tooltip />
                <el-table-column prop="planned_distance_km" label="km" width="70" />
                <el-table-column prop="main_type_raw" label="类型" width="80" />
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </template>
        <el-empty v-else description="暂无草稿，先生成一份训练计划草稿" />
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>历史草稿</h3>
          <p>只显示当前账号生成的 AI 课表草稿。</p>
        </div>
      </div>
      <el-table :data="drafts" v-loading="loadingDrafts" class="history-table">
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="320">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" @click="viewDraft(row.id)">查看</el-button>
              <el-button size="small" type="primary" :disabled="row.status !== 'draft'" @click="apply(row.id)">应用</el-button>
              <el-button size="small" :disabled="row.status !== 'draft'" @click="reject(row.id)">拒绝</el-button>
              <el-dropdown trigger="click" @command="(format) => downloadDraft(row, String(format))">
                <el-button size="small" :icon="Download">导出</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="item in exportOptions" :key="item.value" :command="item.value">
                      {{ item.label }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
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
import { Download } from "@element-plus/icons-vue";

import {
  applyAIPlanDraft,
  exportAIPlanDraft,
  generateAIPlan,
  getAIPlanDraftDetail,
  getAIPlanDrafts,
  getAIPlanQuota,
  rejectAIPlanDraft,
} from "@/api/aiPlan";
import { trackUsageEvent } from "@/api/usageEvents";
import type { AIPlanDraft, AIPlanExportFormat, AIPlanGeneratePayload, AIPlanQuota, RaceDistance } from "@/types/models";

const router = useRouter();
const today = new Date().toISOString().slice(0, 10);
const distanceOptions: Array<{ label: string; value: RaceDistance }> = [
  { label: "1500m", value: "1500m" },
  { label: "3000m", value: "3000m" },
  { label: "5000m", value: "5000m" },
  { label: "10000m", value: "10000m" },
  { label: "半马", value: "half_marathon" },
  { label: "全马", value: "marathon" },
];
const weekDays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const exportOptions: Array<{ label: string; value: AIPlanExportFormat; extension: string }> = [
  { label: "Excel 工作簿", value: "xlsx", extension: "xlsx" },
  { label: "CSV 表格", value: "csv", extension: "csv" },
  { label: "Markdown 文档", value: "markdown", extension: "md" },
  { label: "JSON 数据", value: "json", extension: "json" },
  { label: "日历 ICS", value: "ics", extension: "ics" },
  { label: "Garmin 参考 CSV", value: "garmin_csv", extension: "csv" },
  { label: "高驰参考 CSV", value: "coros_csv", extension: "csv" },
];

const form = reactive<AIPlanGeneratePayload>({
  runner_level: "advanced",
  recent_pb_distance: "5000m",
  recent_pb_result: "00:00:00",
  current_weekly_mileage_km: 80,
  recent_4w_avg_mileage_km: 76,
  available_training_days_per_week: 6,
  can_double_run: false,
  fixed_rest_days: ["周六"],
  injury_notes: "",
  training_preferences: "二四日结构，周日长距离；偏丹尼尔斯和阈值训练，但不做激进双阈值。",
  target_race_name: "眉山东坡马拉松",
  target_race_date: "",
  target_distance: "half_marathon",
  target_result: "00:00:00",
  plan_start_date: today,
  plan_weeks: 8,
  intensity_style: "standard",
  include_pace_guidance: true,
});

const quota = ref<AIPlanQuota | null>(null);
const drafts = ref<AIPlanDraft[]>([]);
const currentDraft = ref<AIPlanDraft | null>(null);
const generating = ref(false);
const applying = ref(false);
const generationProgress = ref(0);
const loadingDrafts = ref(false);
let generationTimer: ReturnType<typeof window.setInterval> | null = null;
let generationStartedAt = 0;

const groupedWorkouts = computed(() => {
  const map = new Map<string, NonNullable<AIPlanDraft["workouts"]>>();
  for (const workout of currentDraft.value?.workouts || []) {
    const key = workout.block_name || "训练块";
    const group = map.get(key) || [];
    group.push(workout);
    map.set(key, group);
  }
  return Array.from(map.entries()).map(([name, items]) => ({ name, items }));
});
const firstWeekGroup = computed(() => groupedWorkouts.value[0] || null);
const restWeekGroups = computed(() => groupedWorkouts.value.slice(1));
const firstWeekDistance = computed(() =>
  (firstWeekGroup.value?.items || []).reduce((sum, item) => sum + Number(item.planned_distance_km || 0), 0).toFixed(1),
);
const firstWeekKeyWorkoutCount = computed(() =>
  (firstWeekGroup.value?.items || []).filter((item) =>
    ["tempo", "interval_speed", "mixed"].includes(item.main_type_normalized),
  ).length,
);
const intensityStyleLabel = computed(() => {
  const labels = { conservative: "保守", standard: "标准", aggressive: "积极" };
  return labels[form.intensity_style] || form.intensity_style;
});

const planEndDate = computed(() => {
  if (!form.plan_start_date || !form.plan_weeks) return "";
  const start = parseLocalDate(form.plan_start_date);
  start.setDate(start.getDate() + form.plan_weeks * 7 - 1);
  return formatLocalDate(start);
});

const raceGapText = computed(() => {
  if (!form.plan_start_date || !form.target_race_date) return "";
  const start = parseLocalDate(form.plan_start_date);
  const race = parseLocalDate(form.target_race_date);
  const days = Math.ceil((race.getTime() - start.getTime()) / 86400000) + 1;
  if (days <= 0) return "";
  return `距目标赛事约 ${days} 天，建议计划周数 ${clamp(Math.ceil(days / 7), 1, 16)} 周`;
});

const dateConstraintError = computed(() => {
  if (!form.plan_start_date || !form.target_race_date) return "";
  const start = parseLocalDate(form.plan_start_date);
  const race = parseLocalDate(form.target_race_date);
  if (race < start) return "目标赛事日期不能早于计划开始日期";
  if (planEndDate.value && parseLocalDate(planEndDate.value) > race) {
    return "当前计划结束日已经晚于目标赛事日期，请减少计划周数或推前开始日期";
  }
  return "";
});

const generationStatusText = computed(() => {
  if (generationProgress.value < 28) return "正在整理跑者信息、目标赛事和训练偏好";
  if (generationProgress.value < 58) return "正在规划周期结构与每周训练重点";
  if (generationProgress.value < 86) return "正在生成每日训练内容和配速建议";
  if (generationProgress.value < 100) return "正在校验草稿并准备预览";
  return "草稿生成完成，正在刷新预览";
});

function parseLocalDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatLocalDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function disableTargetRaceDate(value: Date) {
  if (!form.plan_start_date) return false;
  return value < parseLocalDate(form.plan_start_date);
}

function disablePlanStartDate(value: Date) {
  if (!form.target_race_date) return false;
  return value > parseLocalDate(form.target_race_date);
}

function syncWeeksFromRace() {
  if (!form.plan_start_date || !form.target_race_date) return;
  const start = parseLocalDate(form.plan_start_date);
  const race = parseLocalDate(form.target_race_date);
  const days = Math.ceil((race.getTime() - start.getTime()) / 86400000) + 1;
  if (days <= 0) return;
  form.plan_weeks = clamp(Math.ceil(days / 7), 1, 16);
}

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

function startGenerationProgress() {
  generationProgress.value = 4;
  stopGenerationProgress();
  generationTimer = window.setInterval(() => {
    if (generationProgress.value >= 92) return;
    const step = generationProgress.value < 35 ? 3 : generationProgress.value < 72 ? 2 : 1;
    generationProgress.value = Math.min(generationProgress.value + step, 92);
  }, 2300);
}

function stopGenerationProgress() {
  if (!generationTimer) return;
  window.clearInterval(generationTimer);
  generationTimer = null;
}

async function loadQuota() {
  quota.value = await getAIPlanQuota();
}

async function loadDrafts() {
  loadingDrafts.value = true;
  try {
    drafts.value = await getAIPlanDrafts();
  } finally {
    loadingDrafts.value = false;
  }
}

async function loadAll() {
  await Promise.all([loadQuota(), loadDrafts()]);
}

async function generate() {
  if (dateConstraintError.value) {
    ElMessage.warning(dateConstraintError.value);
    return;
  }
  generating.value = true;
  generationStartedAt = Date.now();
  trackUsageEvent("ai_plan_generate_started");
  startGenerationProgress();
  try {
    const result = await generateAIPlan({
      ...form,
      recent_pb_distance: form.recent_pb_distance || null,
      recent_pb_result: form.recent_pb_result || null,
      injury_notes: form.injury_notes || null,
      training_preferences: form.training_preferences || null,
      target_race_name: form.target_race_name || null,
      target_race_date: form.target_race_date || null,
      target_result: form.target_result || null,
    });
    currentDraft.value = await getAIPlanDraftDetail(result.draft_id);
    generationProgress.value = 100;
    trackUsageEvent("ai_plan_generate_succeeded", { draft_id: result.draft_id });
    ElMessage.success("AI 课表草稿已生成");
    await loadAll();
  } catch (error) {
    const recovered = await recoverDraftAfterUncertainGeneration(error, generationStartedAt);
    if (recovered) {
      generationProgress.value = 100;
      trackUsageEvent("ai_plan_generate_succeeded", { recovered: true });
      ElMessage.success("AI 课表草稿已生成，已自动刷新预览");
      return;
    }
    trackUsageEvent("ai_plan_generate_failed", { error_type: "request_failed" });
    ElMessage.error(getGenerateErrorMessage(error));
  } finally {
    stopGenerationProgress();
    window.setTimeout(() => {
      generating.value = false;
      generationProgress.value = 0;
    }, 350);
  }
}

function isUncertainGenerationError(error: unknown) {
  const err = error as {
    code?: string;
    message?: string;
    response?: { status?: number };
  };
  const status = err?.response?.status || 0;
  return err?.code === "ECONNABORTED" || status >= 500;
}

function getGenerateErrorMessage(error: unknown) {
  const err = error as {
    code?: string;
    message?: string;
    response?: { status?: number; data?: { message?: string } };
  };
  if (isUncertainGenerationError(error)) {
    return "AI 生成请求耗时较长或模型服务暂时不可用。已刷新历史草稿，请稍后再查看或重新生成。";
  }
  return err?.response?.data?.message || err?.message || "AI 课表生成失败，请稍后重试。";
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function recoverDraftAfterUncertainGeneration(error: unknown, startedAt: number) {
  if (!isUncertainGenerationError(error)) return false;
  const earliest = startedAt - 2 * 60 * 1000;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (attempt > 0) await sleep(3500);
    try {
      await loadAll();
    } catch {
      continue;
    }
    const candidate = drafts.value.find((draft) => {
      const createdAt = new Date(draft.created_at).getTime();
      return Number.isFinite(createdAt) && createdAt >= earliest;
    });
    if (candidate) {
      currentDraft.value = await getAIPlanDraftDetail(candidate.id);
      return true;
    }
  }
  return false;
}

async function viewDraft(id: number) {
  currentDraft.value = await getAIPlanDraftDetail(id);
}

async function apply(id: number) {
  if (applying.value) return;
  applying.value = true;
  try {
    const result = await applyAIPlanDraft(id);
    trackUsageEvent("ai_plan_applied", { draft_id: id, cycle_id: result.cycle_id });
    ElMessage.success("计划已采用，接下来从今天的训练开始。");
    await router.push("/today");
  } finally {
    applying.value = false;
  }
}

async function reject(id: number) {
  const result = await rejectAIPlanDraft(id);
  ElMessage.success(result.message);
  await loadAll();
  currentDraft.value = await getAIPlanDraftDetail(id);
}

async function downloadDraft(draft: AIPlanDraft, format: string) {
  const exportFormat = format as AIPlanExportFormat;
  const option = exportOptions.find((item) => item.value === exportFormat);
  const blob = await exportAIPlanDraft(draft.id, exportFormat);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeFilename(draft.title || `ai-plan-${draft.id}`)}.${option?.extension || "txt"}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

async function downloadCurrentDraft(format: string) {
  if (!currentDraft.value) return;
  await downloadDraft(currentDraft.value, format);
}

function safeFilename(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, "-").replace(/\s+/g, "-").slice(0, 80) || "ai-plan-draft";
}

onMounted(loadAll);
onBeforeUnmount(stopGenerationProgress);
</script>

<style scoped>
.ai-plan-page .panel {
  padding: 22px;
}

.ai-plan-page {
  position: relative;
}

.generation-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(3px);
}

.generation-panel {
  display: grid;
  gap: 16px;
  width: min(460px, 100%);
  padding: 24px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.28);
}

.generation-spinner {
  width: 42px;
  height: 42px;
  border: 4px solid #d7e7f4;
  border-top-color: #1976d2;
  border-radius: 50%;
  animation: generation-spin 1.6s linear infinite;
}

.generation-copy {
  display: grid;
  gap: 6px;
}

.generation-copy h3 {
  margin: 0;
  color: #172033;
  font-size: 20px;
}

.generation-copy p,
.generation-meta {
  margin: 0;
  color: #667085;
  font-size: 13px;
}

.generation-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.generation-mask-enter-active,
.generation-mask-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.generation-mask-enter-from,
.generation-mask-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

@keyframes generation-spin {
  to {
    transform: rotate(360deg);
  }
}

.ai-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--shadow-sm);
}

.hero-kicker {
  margin-bottom: 8px;
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.ai-hero h2 {
  margin: 0;
  color: #172033;
  font-size: 26px;
}

.ai-hero p {
  max-width: 880px;
  margin: 8px 0 0;
  color: #667085;
  line-height: 1.7;
}

.quota-box {
  display: grid;
  gap: 4px;
  min-width: 190px;
  padding: 12px 14px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: #f6fbff;
}

.quota-box span,
.quota-box em {
  color: #667085;
  font-size: 12px;
  font-style: normal;
}

.quota-box strong {
  color: #1976d2;
}

.ai-grid {
  display: grid;
  grid-template-columns: minmax(460px, 0.95fr) minmax(420px, 1.05fr);
  gap: 16px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-head h3 {
  margin: 0;
  color: #1f2937;
  font-size: 17px;
  font-weight: 650;
}

.panel-head p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-help {
  margin-top: 6px;
  color: #667085;
  font-size: 12px;
  line-height: 1.5;
}

.preference-link {
  display: inline-flex;
  margin-top: 8px;
  color: #1976d2;
  font-weight: 700;
  text-decoration: none;
}

.advanced-collapse {
  margin-bottom: 16px;
}

.date-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: -2px 0 18px;
  padding: 14px 16px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: linear-gradient(135deg, #f7fbff, #ffffff);
}

.date-summary.invalid {
  border-color: #ffd1ca;
  background: #fff7f5;
}

.date-summary-main {
  display: grid;
  gap: 4px;
}

.date-summary-main .label {
  color: #667085;
  font-size: 12px;
}

.date-summary-main strong {
  color: #172033;
  font-size: 20px;
}

.date-summary-meta {
  display: grid;
  gap: 4px;
  color: #667085;
  font-size: 13px;
  text-align: right;
}

.date-summary.invalid .date-summary-meta {
  color: #b42318;
}

.form-actions,
.draft-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.draft-summary-card {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
  padding: 16px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: #f8fbff;
}

.draft-summary-card h4,
.week-block h4 {
  margin: 0;
  color: #172033;
}

.draft-summary-card p {
  margin: 0;
  color: #667085;
}

.draft-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.draft-metrics span {
  display: grid;
  gap: 3px;
  padding: 10px;
  border: 1px solid #e5edf6;
  border-radius: 6px;
  background: #ffffff;
  color: #344054;
  font-size: 13px;
}

.draft-metrics b {
  color: #667085;
  font-size: 12px;
}

.export-note {
  margin: 8px 0 0;
  color: #667085;
  font-size: 12px;
  line-height: 1.6;
  text-align: right;
}

.week-block {
  margin-top: 18px;
}

.table-actions {
  display: flex;
  gap: 8px;
}

.history-table {
  width: 100%;
}

@media (max-width: 1180px) {
  .ai-grid,
  .form-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .ai-plan-page {
    gap: 12px;
  }

  .ai-plan-page .panel,
  .ai-hero {
    padding: 16px;
  }

  .ai-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .ai-hero h2 {
    font-size: 22px;
  }

  .ai-hero p {
    font-size: 13px;
    line-height: 1.65;
  }

  .quota-box {
    min-width: 0;
  }

  .date-summary {
    align-items: flex-start;
    flex-direction: column;
    padding: 12px;
  }

  .date-summary-meta {
    text-align: left;
  }

  .form-actions,
  .draft-actions,
  .table-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .form-actions .el-button,
  .draft-actions .el-button,
  .table-actions .el-button {
    width: 100%;
    margin-left: 0;
  }

  .draft-actions :deep(.el-dropdown),
  .table-actions :deep(.el-dropdown) {
    width: 100%;
  }

  .export-note {
    text-align: left;
  }

  .week-block {
    overflow-x: auto;
  }

  .week-block :deep(.el-table),
  .history-table {
    min-width: 620px;
  }

  .generation-panel {
    padding: 20px;
  }

  .generation-meta {
    flex-direction: column;
    gap: 4px;
  }
}
</style>
