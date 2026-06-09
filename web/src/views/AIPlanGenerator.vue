<template>
  <div class="page-stack ai-plan-page">
    <section class="ai-hero">
      <div>
        <div class="hero-kicker">AI Plan Draft</div>
        <h2>AI 课表草稿生成器</h2>
        <p>AI 生成的训练计划仅作为草稿建议，请结合自身状态、伤病情况和教练意见调整后再执行。</p>
      </div>
      <div class="quota-box">
        <span>{{ quota?.model_name || "deepseek-v4-flash" }}</span>
        <strong>今日剩余 {{ quota?.remaining_count ?? "-" }} 次</strong>
        <em>冷却 {{ quota?.cooldown_seconds ?? 60 }} 秒</em>
      </div>
    </section>

    <section class="ai-grid">
      <article class="panel ai-form-card">
        <div class="panel-head">
          <div>
            <h3>跑者与目标信息</h3>
            <p>信息越具体，草稿越接近你的真实训练节奏。</p>
          </div>
        </div>

        <el-form label-position="top" class="ai-form">
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
            <el-form-item label="近期 PB 距离">
              <el-select v-model="form.recent_pb_distance" clearable style="width: 100%">
                <el-option v-for="item in distanceOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="近期 PB 成绩">
              <el-input v-model="form.recent_pb_result" placeholder="例如 16:24、1:12:32" />
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="当前周跑量 km">
              <el-input-number v-model="form.current_weekly_mileage_km" :min="0" :max="300" style="width: 100%" />
            </el-form-item>
            <el-form-item label="最近 4 周平均跑量 km">
              <el-input-number v-model="form.recent_4w_avg_mileage_km" :min="0" :max="300" style="width: 100%" />
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="每周可训练天数">
              <el-input-number v-model="form.available_training_days_per_week" :min="1" :max="7" style="width: 100%" />
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

          <div class="form-row">
            <el-form-item label="目标赛事名称">
              <el-input v-model="form.target_race_name" placeholder="眉山东坡半马" />
            </el-form-item>
            <el-form-item label="目标赛事日期">
              <el-date-picker v-model="form.target_race_date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="目标距离">
              <el-select v-model="form.target_distance" style="width: 100%">
                <el-option v-for="item in distanceOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标成绩">
              <el-input v-model="form.target_result" placeholder="例如 1:11:30" />
            </el-form-item>
          </div>

          <div class="form-row">
            <el-form-item label="计划开始日期">
              <el-date-picker v-model="form.plan_start_date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
            <el-form-item label="计划周数">
              <el-input-number v-model="form.plan_weeks" :min="1" :max="16" style="width: 100%" />
            </el-form-item>
          </div>

          <el-form-item label="伤病说明">
            <el-input
              v-model="form.injury_notes"
              type="textarea"
              :rows="2"
              placeholder="例如：左小腿偶有紧张，无明显疼痛"
            />
          </el-form-item>
          <el-form-item label="训练偏好">
            <el-input
              v-model="form.training_preferences"
              type="textarea"
              :rows="2"
              placeholder="例如：二四日结构，周日长距离"
            />
          </el-form-item>
          <el-form-item label="包含配速建议">
            <el-switch v-model="form.include_pace_guidance" />
          </el-form-item>

          <div class="form-actions">
            <el-button type="primary" :loading="generating" :disabled="!quota?.can_generate" @click="generate">
              生成草稿
            </el-button>
            <el-button @click="loadAll">刷新额度/草稿</el-button>
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
          <div class="draft-summary">
            <h4>{{ currentDraft.title }}</h4>
            <p>{{ currentDraft.goal }}</p>
            <p>{{ currentDraft.summary }}</p>
            <el-alert
              v-if="currentDraft.risk_notes?.length"
              type="warning"
              :closable="false"
              :title="currentDraft.risk_notes.join('；')"
            />
          </div>
          <div class="draft-actions">
            <el-button type="primary" :disabled="currentDraft.status !== 'draft'" @click="apply(currentDraft.id)">
              应用为正式计划
            </el-button>
            <el-button :disabled="currentDraft.status !== 'draft'" @click="reject(currentDraft.id)">拒绝草稿</el-button>
          </div>
          <div v-for="group in groupedWorkouts" :key="group.name" class="week-block">
            <h4>{{ group.name }}</h4>
            <el-table :data="group.items" size="small">
              <el-table-column prop="workout_date" label="日期" width="110" />
              <el-table-column prop="weekday" label="星期" width="70" />
              <el-table-column prop="planned_content" label="训练内容" min-width="220" show-overflow-tooltip />
              <el-table-column prop="planned_distance_km" label="km" width="70" />
              <el-table-column prop="main_type_raw" label="类型" width="80" />
              <el-table-column prop="target_pace_text" label="目标配速" width="130" show-overflow-tooltip />
            </el-table>
          </div>
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
      <el-table :data="drafts" v-loading="loadingDrafts">
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" @click="viewDraft(row.id)">查看</el-button>
              <el-button size="small" type="primary" :disabled="row.status !== 'draft'" @click="apply(row.id)">应用</el-button>
              <el-button size="small" :disabled="row.status !== 'draft'" @click="reject(row.id)">拒绝</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  applyAIPlanDraft,
  generateAIPlan,
  getAIPlanDraftDetail,
  getAIPlanDrafts,
  getAIPlanQuota,
  rejectAIPlanDraft,
} from "@/api/aiPlan";
import type { AIPlanDraft, AIPlanGeneratePayload, AIPlanQuota, RaceDistance } from "@/types/models";

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

const form = reactive<AIPlanGeneratePayload>({
  runner_level: "advanced",
  recent_pb_distance: "5000m",
  recent_pb_result: "16:24",
  current_weekly_mileage_km: 80,
  recent_4w_avg_mileage_km: 76,
  available_training_days_per_week: 6,
  can_double_run: false,
  fixed_rest_days: ["周一"],
  injury_notes: "",
  training_preferences: "二四日结构，周日长距离",
  target_race_name: "目标半马",
  target_race_date: "",
  target_distance: "half_marathon",
  target_result: "1:11:30",
  plan_start_date: today,
  plan_weeks: 8,
  intensity_style: "standard",
  include_pace_guidance: true,
});

const quota = ref<AIPlanQuota | null>(null);
const drafts = ref<AIPlanDraft[]>([]);
const currentDraft = ref<AIPlanDraft | null>(null);
const generating = ref(false);
const loadingDrafts = ref(false);

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

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
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
  generating.value = true;
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
    ElMessage.success("AI 课表草稿已生成");
    await loadAll();
  } finally {
    generating.value = false;
  }
}

async function viewDraft(id: number) {
  currentDraft.value = await getAIPlanDraftDetail(id);
}

async function apply(id: number) {
  const result = await applyAIPlanDraft(id);
  ElMessage.success(result.message);
  await loadAll();
  currentDraft.value = await getAIPlanDraftDetail(id);
}

async function reject(id: number) {
  const result = await rejectAIPlanDraft(id);
  ElMessage.success(result.message);
  await loadAll();
  currentDraft.value = await getAIPlanDraftDetail(id);
}

onMounted(loadAll);
</script>

<style scoped>
.ai-plan-page .panel {
  padding: 22px;
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
  margin: 8px 0 0;
  color: #667085;
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

.form-actions,
.draft-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.draft-summary {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.draft-summary h4,
.week-block h4 {
  margin: 0;
  color: #172033;
}

.draft-summary p {
  margin: 0;
  color: #667085;
}

.week-block {
  margin-top: 18px;
}

.table-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 1180px) {
  .ai-grid,
  .form-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .ai-hero {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
