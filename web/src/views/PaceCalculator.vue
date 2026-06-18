<template>
  <div class="page-stack pace-calculator-page">
    <PageHeader title="配速计算器" subtitle="用近期比赛成绩估算 VDOT，生成 REC、E、M、T1、T2、I、R 训练配速区间。">
      <template #actions><el-button :icon="Refresh" @click="loadProfiles">刷新档案</el-button></template>
    </PageHeader>

    <section class="calculator-grid">
      <article class="panel input-panel">
        <div class="panel-head">
          <div>
            <h3>比赛成绩输入</h3>
            <p>训练配速默认基于你的实际比赛成绩推算。年龄和性别仅用于表现水平参考，不直接替代当前训练能力。</p>
          </div>
        </div>

        <el-form label-position="top" class="calculator-form">
          <el-form-item label="配速档案名称">
            <el-input v-model="form.name" placeholder="半马 PB 1:12:32" />
          </el-form-item>

          <div class="form-row">
            <el-form-item label="比赛距离">
              <el-select v-model="form.race_distance" style="width: 100%">
                <el-option
                  v-for="item in raceDistanceOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="比赛成绩">
              <el-time-picker
                v-model="raceResultTime"
                value-format="HH:mm:ss"
                format="HH:mm:ss"
                :default-value="new Date(2000, 0, 1, 0, 0, 0)"
                :clearable="false"
                placeholder="选择成绩"
                style="width: 100%"
              />
            </el-form-item>
          </div>

          <el-collapse class="advanced-collapse">
            <el-collapse-item title="年龄 / 性别参考分析" name="age-reference">
              <div class="form-row">
                <el-form-item label="年龄">
                  <el-input-number v-model="form.age" :min="5" :max="120" style="width: 100%" />
                </el-form-item>
                <el-form-item label="性别">
                  <el-select v-model="form.sex" style="width: 100%">
                    <el-option label="未知 / 暂不提供" value="unknown" />
                    <el-option label="男性" value="male" />
                    <el-option label="女性" value="female" />
                  </el-select>
                </el-form-item>
              </div>
              <p class="reference-note">
                年龄参考分析会单独展示年龄等级、公开组等效成绩和参考标签；训练配速区间仍按你的实际比赛成绩生成。
              </p>
            </el-collapse-item>
          </el-collapse>
<!-- 
          <div class="quick-times">
            <button type="button" @click="setRaceResult('00:16:24')">5K 16:24</button>
            <button type="button" @click="setRaceResult('01:12:32')">半马 1:12:32</button>
            <button type="button" @click="setRaceResult('02:54:00')">全马 2:54:00</button>
          </div> -->

          <div class="form-actions">
            <el-button type="primary" :loading="calculating" @click="handleCalculate">计算</el-button>
            <el-button :loading="saving" @click="handleSave">保存档案</el-button>
          </div>
        </el-form>
      </article>

      <article class="panel result-panel">
        <div class="panel-head">
          <div>
            <h3>计算结果</h3>
          <p>第一版为近似 VDOT，用于训练配速参考。</p>
          </div>
          <span class="algorithm-badge">approx_vdot_v1</span>
        </div>

        <div v-if="calculation" class="result-metrics">
          <div class="vdot-card">
            <span>VDOT</span>
            <strong>{{ Number(calculation.vdot).toFixed(1) }}</strong>
          </div>
          <div class="result-line">
            <span>比赛距离</span>
            <b>{{ raceLabel(calculation.race_distance) }}</b>
          </div>
          <div class="result-line">
            <span>比赛成绩</span>
            <b>{{ formatDuration(calculation.race_result_seconds) }}</b>
          </div>
          <div class="age-reference-box">
            <span>年龄参考分析</span>
            <template v-if="calculation.age_grading">
              <div class="age-reference-grid">
                <div>
                  <small>年龄等级</small>
                  <strong>{{ Number(calculation.age_grading.age_grade_percent).toFixed(1) }}%</strong>
                </div>
                <div>
                  <small>公开组等效成绩</small>
                  <strong>{{ formatDuration(calculation.age_grading.age_graded_seconds) }}</strong>
                </div>
                <div>
                  <small>年龄系数</small>
                  <strong>{{ Number(calculation.age_grading.age_factor).toFixed(3) }}</strong>
                </div>
                <div>
                  <small>参考标签</small>
                  <strong>{{ calculation.age_grading.level_label }}</strong>
                </div>
              </div>
              <p>{{ calculation.age_grading.note }}</p>
            </template>
            <p v-else>{{ calculation.age_reference || "未填写年龄/性别；训练配速按实际比赛成绩推算。" }}</p>
          </div>
        </div>

        <div v-else class="empty-result">
          <span>00:00:00</span>
          <p>选择比赛距离和成绩后点击计算。</p>
        </div>
      </article>
    </section>

    <section class="panel zones-panel">
      <div class="panel-head">
        <div>
          <h3>训练配速区间</h3>
          <p>配速建议用于训练参考，不代表必须严格执行。疲劳、天气、地形和身体状态都会影响实际配速。</p>
        </div>
      </div>
      <el-table :data="calculation?.zones || []" empty-text="暂无计算结果">
        <el-table-column prop="zone_code" label="区间" width="90" />
        <el-table-column prop="zone_name" label="名称" width="170" />
        <el-table-column prop="target_pace_text" label="配速范围" width="180" />
        <el-table-column prop="description" label="说明" min-width="300" show-overflow-tooltip />
      </el-table>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>历史配速档案</h3>
          <p>保存后的档案可以一键写入当前用户的配速规则。</p>
        </div>
      </div>
      <el-table :data="profiles" v-loading="loadingProfiles">
        <el-table-column prop="name" label="档案名称" min-width="190" />
        <el-table-column label="距离" width="120">
          <template #default="{ row }">{{ raceLabel(row.race_distance) }}</template>
        </el-table-column>
        <el-table-column label="成绩" width="120">
          <template #default="{ row }">{{ formatDuration(row.race_result_seconds) }}</template>
        </el-table-column>
        <el-table-column label="VDOT" width="100">
          <template #default="{ row }">{{ Number(row.vdot).toFixed(1) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" @click="loadProfileDetail(row.id)">查看详情</el-button>
              <el-button size="small" type="primary" @click="applyToRules(row.id)">应用到规则</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="removeProfile(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="detailVisible" title="配速档案详情" width="760px">
      <div v-if="selectedProfile" class="profile-detail">
        <div class="detail-title">
          <strong>{{ selectedProfile.name }}</strong>
          <span>VDOT {{ Number(selectedProfile.vdot).toFixed(1) }}</span>
        </div>
        <el-table :data="selectedProfile.zones || []">
          <el-table-column prop="zone_code" label="区间" width="90" />
          <el-table-column prop="zone_name" label="名称" width="150" />
          <el-table-column prop="target_pace_text" label="配速范围" width="170" />
          <el-table-column prop="description" label="说明" min-width="240" show-overflow-tooltip />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="selectedProfile" type="primary" @click="applyToRules(selectedProfile.id)">
          应用到配速规则
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Delete, Refresh } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";

import {
  applyPaceProfileToRules,
  calculatePaces,
  createPaceProfile,
  deletePaceProfile,
  getPaceProfile,
  listPaceProfiles,
} from "@/api/paceCalculator";
import type { PaceCalculationResult, PaceProfile, RaceDistance } from "@/types/models";

interface PaceCalculatorForm {
  name: string;
  race_distance: RaceDistance;
  age: number | null;
  sex: "male" | "female" | "unknown";
}

const router = useRouter();

const raceDistanceOptions: Array<{ label: string; value: RaceDistance }> = [
  { label: "1500m", value: "1500m" },
  { label: "3000m", value: "3000m" },
  { label: "5000m", value: "5000m" },
  { label: "10000m", value: "10000m" },
  { label: "半马", value: "half_marathon" },
  { label: "全马", value: "marathon" },
];

const form = reactive<PaceCalculatorForm>({
  name: "半马 PB 1:12:32",
  race_distance: "half_marathon",
  age: null,
  sex: "unknown",
});

const raceResultTime = ref("00:00:00");
const calculation = ref<PaceCalculationResult | null>(null);
const profiles = ref<PaceProfile[]>([]);
const selectedProfile = ref<PaceProfile | null>(null);
const calculating = ref(false);
const saving = ref(false);
const loadingProfiles = ref(false);
const detailVisible = ref(false);

function raceLabel(value: RaceDistance) {
  return raceDistanceOptions.find((item) => item.value === value)?.label || value;
}

function normalizeRaceResult() {
  return raceResultTime.value || "00:00:00";
}

function setRaceResult(value: string) {
  raceResultTime.value = value;
}

function formatDuration(seconds: number) {
  const hour = Math.floor(seconds / 3600);
  const minute = Math.floor((seconds % 3600) / 60);
  const second = seconds % 60;
  if (hour > 0) return `${hour}:${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}`;
  return `${minute}:${String(second).padStart(2, "0")}`;
}

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

async function handleCalculate() {
  calculating.value = true;
  try {
    calculation.value = await calculatePaces({
      race_distance: form.race_distance,
      race_result: normalizeRaceResult(),
      age: form.age,
      sex: form.sex,
    });
  } finally {
    calculating.value = false;
  }
}

async function handleSave() {
  saving.value = true;
  try {
    await createPaceProfile({
      name: form.name,
      race_distance: form.race_distance,
      race_result: normalizeRaceResult(),
      age: form.age,
      sex: form.sex,
    });
    calculation.value = await calculatePaces({
      race_distance: form.race_distance,
      race_result: normalizeRaceResult(),
      age: form.age,
      sex: form.sex,
    });
    ElMessage.success("配速档案已保存");
    await loadProfiles();
  } finally {
    saving.value = false;
  }
}

async function loadProfiles() {
  loadingProfiles.value = true;
  try {
    profiles.value = await listPaceProfiles();
  } finally {
    loadingProfiles.value = false;
  }
}

async function loadProfileDetail(id: number) {
  selectedProfile.value = await getPaceProfile(id);
  detailVisible.value = true;
}

async function applyToRules(id: number) {
  const result = await applyPaceProfileToRules(id);
  ElMessage.success(result.message || "已更新配速规则");
  detailVisible.value = false;
  router.push("/pace-rules");
}

async function removeProfile(row: PaceProfile) {
  await ElMessageBox.confirm(`确认删除配速档案「${row.name}」？`, "删除确认", {
    type: "warning",
    confirmButtonText: "删除",
    cancelButtonText: "取消",
  });
  await deletePaceProfile(row.id);
  ElMessage.success("配速档案已删除");
  await loadProfiles();
}

onMounted(() => {
  loadProfiles();
});
</script>

<style scoped>
.pace-calculator-page {
  gap: 16px;
}

.pace-calculator-page .panel {
  padding: 22px;
}

.calculator-hero {
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

.calculator-hero h2 {
  margin: 0;
  color: #172033;
  font-size: 26px;
  line-height: 1.2;
}

.calculator-hero p {
  margin: 8px 0 0;
  color: #667085;
}

.calculator-grid {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) minmax(340px, 0.78fr);
  gap: 16px;
  align-items: stretch;
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

.calculator-form {
  display: grid;
  gap: 2px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.advanced-collapse {
  margin-bottom: 12px;
}

.reference-note {
  margin: 0 0 4px;
  color: #667085;
  font-size: 13px;
  line-height: 1.7;
}

.quick-times {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: -2px 0 12px;
}

.quick-times button {
  height: 30px;
  padding: 0 10px;
  border: 1px solid #d7e7f4;
  border-radius: 999px;
  color: #1976d2;
  background: #f6fbff;
  cursor: pointer;
}

.quick-times button:hover {
  border-color: #1976d2;
  background: #e7f1f8;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 4px;
}

.result-panel {
  display: flex;
  flex-direction: column;
}

.algorithm-badge {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  color: #1976d2;
  background: #e7f1f8;
  font-size: 12px;
  font-weight: 700;
}

.result-metrics {
  display: grid;
  gap: 12px;
}

.vdot-card {
  padding: 24px;
  border: 1px solid #d7e7f4;
  border-radius: 8px;
  background: linear-gradient(135deg, #f6fbff, #ffffff);
}

.vdot-card span,
.result-line span {
  color: #667085;
  font-size: 13px;
}

.vdot-card strong {
  display: block;
  margin-top: 8px;
  color: #1976d2;
  font-size: 44px;
  line-height: 1;
}

.result-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: #f8fafc;
}

.result-line b {
  color: #172033;
}

.age-reference-box {
  padding: 12px 14px;
  border: 1px solid #d7e7f4;
  border-radius: 6px;
  background: #f6fbff;
}

.age-reference-box span {
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.age-reference-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.age-reference-grid div {
  min-width: 0;
  padding: 10px;
  border-radius: 6px;
  background: #ffffff;
}

.age-reference-grid small {
  display: block;
  color: #667085;
  font-size: 12px;
}

.age-reference-grid strong {
  display: block;
  margin-top: 4px;
  color: #172033;
  font-size: 15px;
  line-height: 1.35;
  word-break: break-word;
}

.age-reference-box p {
  margin: 6px 0 0;
  color: #475467;
  font-size: 13px;
  line-height: 1.7;
}

.empty-result {
  display: grid;
  flex: 1;
  place-items: center;
  align-content: center;
  min-height: 214px;
  color: #98a2b3;
  text-align: center;
}

.empty-result span {
  color: #d0d5dd;
  font-size: 42px;
  font-weight: 700;
  line-height: 1;
}

.empty-result p {
  margin: 12px 0 0;
}

.zones-panel {
  padding-bottom: 20px;
}

.profile-detail {
  display: grid;
  gap: 14px;
}

.detail-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f8fafc;
}

.detail-title span {
  color: #1976d2;
  font-weight: 700;
}

@media (max-width: 1080px) {
  .calculator-grid,
  .form-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .calculator-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .form-actions {
    justify-content: stretch;
  }

  .form-actions .el-button {
    flex: 1;
  }

  .age-reference-grid {
    grid-template-columns: 1fr;
  }
}
</style>
