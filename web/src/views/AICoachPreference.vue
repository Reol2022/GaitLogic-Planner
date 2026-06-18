<template>
  <div class="page-stack coach-page">
    <PageHeader title="AI 教练偏好配置" subtitle="这些设置会作为你的训练哲学写入 AI 课表 Prompt。安全规则始终优先于偏好配置。">
      <template #actions><el-button type="primary" :loading="saving" @click="savePreference">保存配置</el-button></template>
    </PageHeader>

    <section class="coach-grid">
      <article class="panel">
        <div class="panel-head">
          <h3>训练体系偏好</h3>
          <p>选择你更愿意让 AI 参考的训练思想，可多选。</p>
        </div>
        <el-checkbox-group v-model="form.preferred_training_systems" class="system-options">
          <el-checkbox-button v-for="item in trainingSystems" :key="item" :label="item" />
        </el-checkbox-group>

        <el-form label-position="top" class="form-block">
          <el-form-item label="强度保守度">
            <el-segmented v-model="form.intensity_conservatism" :options="intensityOptions" />
          </el-form-item>
          <el-form-item label="禁用训练类型">
            <el-select v-model="form.disabled_workout_types" multiple clearable style="width: 100%">
              <el-option v-for="item in workoutTypes" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="双跑策略">
            <el-radio-group v-model="form.double_run_policy">
              <el-radio-button label="never">不安排</el-radio-button>
              <el-radio-button label="cautious">谨慎安排</el-radio-button>
              <el-radio-button label="allowed">允许安排</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>训练习惯</h3>
          <p>告诉 AI 你更习惯怎样排关键课、休息日和长距离。</p>
        </div>
        <el-form label-position="top">
          <el-form-item label="关键课习惯">
            <el-input
              v-model="form.key_workout_habit"
              type="textarea"
              :rows="3"
              placeholder="例如：每周二阈值、周四速度或专项、周日长距离；关键课最多 2 次。"
            />
          </el-form-item>
          <el-form-item label="休息日策略">
            <el-input
              v-model="form.rest_day_strategy"
              type="textarea"
              :rows="3"
              placeholder="例如：周一优先休息；疲劳时用 REC 替代 E；赛前一周增加恢复。"
            />
          </el-form-item>
          <el-form-item label="长距离策略">
            <el-input
              v-model="form.long_run_strategy"
              type="textarea"
              :rows="3"
              placeholder="例如：长距离控制在周跑量 25%-30%，不经常跑成强度课。"
            />
          </el-form-item>
        </el-form>
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>风险控制与补充说明</h3>
        <p>这里适合写你的伤病边界、恢复偏好，以及不希望 AI 触碰的安排方式。</p>
      </div>
      <el-form label-position="top">
        <el-form-item label="伤病风险策略">
          <el-input
            v-model="form.injury_risk_policy"
            type="textarea"
            :rows="3"
            placeholder="例如：小腿或跟腱紧张时取消 I/R；连续疲劳时优先保留轻松跑和休息。"
          />
        </el-form-item>
        <el-form-item label="额外说明">
          <el-input
            v-model="form.additional_notes"
            type="textarea"
            :rows="4"
            placeholder="例如：更偏半马专项耐力，不喜欢灰区慢性堆强度；希望所有关键课都写明目的。"
          />
        </el-form-item>
      </el-form>
      <div class="footer-actions">
        <el-button @click="loadPreference">恢复已保存配置</el-button>
        <el-button type="primary" :loading="saving" @click="savePreference">保存配置</el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { getAICoachPreference, updateAICoachPreference } from "@/api/aiCoachPreference";
import type { AICoachPreferencePayload } from "@/types/models";

const trainingSystems = [
  "丹尼尔斯",
  "阈值训练",
  "极化训练",
  "挪威双阈值",
  "卡诺瓦专项",
  "经典周期化",
];

const workoutTypes = [
  { label: "REC 恢复跑", value: "REC" },
  { label: "E 轻松跑", value: "E" },
  { label: "LSD 长距离", value: "LSD" },
  { label: "M 稳态/马拉松强度", value: "M" },
  { label: "T1 稳阈值", value: "T1" },
  { label: "T2 高阈值", value: "T2" },
  { label: "I 间歇", value: "I" },
  { label: "R 短速度", value: "R" },
  { label: "Mixed 混合训练", value: "Mixed" },
];

const intensityOptions = [
  { label: "保守", value: "conservative" },
  { label: "标准", value: "standard" },
  { label: "积极", value: "aggressive" },
  { label: "自定义", value: "custom" },
];

const form = reactive<AICoachPreferencePayload>({
  preferred_training_systems: ["丹尼尔斯", "阈值训练", "经典周期化"],
  intensity_conservatism: "standard",
  key_workout_habit: "",
  rest_day_strategy: "",
  disabled_workout_types: [],
  double_run_policy: "cautious",
  long_run_strategy: "",
  injury_risk_policy: "",
  additional_notes: "",
});

const saving = ref(false);

function assignForm(payload: AICoachPreferencePayload) {
  form.preferred_training_systems = payload.preferred_training_systems || [];
  form.intensity_conservatism = payload.intensity_conservatism || "standard";
  form.key_workout_habit = payload.key_workout_habit || "";
  form.rest_day_strategy = payload.rest_day_strategy || "";
  form.disabled_workout_types = payload.disabled_workout_types || [];
  form.double_run_policy = payload.double_run_policy || "cautious";
  form.long_run_strategy = payload.long_run_strategy || "";
  form.injury_risk_policy = payload.injury_risk_policy || "";
  form.additional_notes = payload.additional_notes || "";
}

async function loadPreference() {
  const result = await getAICoachPreference();
  assignForm(result);
}

async function savePreference() {
  saving.value = true;
  try {
    const result = await updateAICoachPreference({ ...form });
    assignForm(result);
    ElMessage.success("AI 教练偏好已保存");
  } finally {
    saving.value = false;
  }
}

onMounted(loadPreference);
</script>

<style scoped>
.coach-hero {
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

.coach-hero span {
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.coach-hero h2 {
  margin: 8px 0 0;
  color: #172033;
  font-size: 26px;
}

.coach-hero p {
  margin: 8px 0 0;
  color: #667085;
}

.coach-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.panel {
  padding: 22px;
}

.panel-head {
  margin-bottom: 16px;
}

.panel-head h3 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

.panel-head p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.system-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
}

.form-block {
  margin-top: 10px;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1080px) {
  .coach-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .coach-hero {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
