<template>
  <main class="welcome-page">
    <ol class="guide-steps" aria-label="开始使用步骤"><li v-for="(label,index) in ['选择方式','设备连接','开始训练']" :key="label" :class="{active:step===index+1,done:step>index+1}" :aria-current="step===index+1?'step':undefined"><span>{{index+1}}</span>{{label}}</li></ol>
    <section class="welcome-hero">
      <p>让训练从这里开始 · 第 {{ step }} / 3 步</p>
      <h1>{{ step === 1 ? '你现在想先做什么？' : step === 2 ? '设备连接可以稍后完成' : '准备好开始了' }}</h1>
      <span>已有课表就直接导入，需要计划就从目标开始。也可以只记录训练，不必先建立周期。</span>
    </section>

    <section v-if="step === 1" class="welcome-grid" aria-label="选择开始方式">
      <button type="button" class="welcome-card primary" @click="choose('ai')">
        <strong>AI 帮我制定计划</strong>
        <span>根据当前能力、跑量和比赛目标生成计划草稿。</span>
      </button>
      <button type="button" class="welcome-card" @click="choose('import')">
        <strong>导入已有课表</strong>
        <span>支持 Excel、CSV、TXT、Markdown 和 JSON。</span>
      </button>
      <button type="button" class="welcome-card" @click="choose('record')">
        <strong>先记录和了解训练</strong>
        <span>连接设备或导入实际活动，不强制创建训练计划。</span>
      </button>
    </section>

    <section v-else-if="step === 2" class="panel guide-panel">
      <h2>已有运动手表？</h2>
      <p>你可以先连接设备，也可以保留手动记录的习惯。设备缺少的主观感受仍由你补充。</p>
      <div class="guide-actions"><el-button type="primary" @click="connectDevice">先连接设备</el-button>
      <el-button @click="step = 3">稍后连接，继续</el-button></div>
      <p class="guide-note">连接设备不会自动应用 AI 计划；遇到失败时仍可继续使用其他功能。</p>
    </section>
    <section v-else class="panel guide-panel">
      <h2>{{ mode === 'import' ? '导入 → 预览 → 确认课表' : mode === 'ai' ? '填写目标 → 预览草稿 → 确认开始' : '同步或导入 → 确认活动 → 补充感受' }}</h2>
      <p>正式课表只会在你明确确认后改变。没有设备或部分恢复数据缺失，也可以先使用可用功能。</p>
      <el-button type="primary" @click="finish">{{ mode === 'record' ? '查看记录入口' : '继续设置计划' }}</el-button>
    </section>
    <div class="guide-footer">
      <button v-if="step > 1" class="skip-button" type="button" @click="step--">返回上一步</button>
      <button class="skip-button" type="button" @click="skip">暂时跳过，进入今日</button>
      <router-link to="/cycles" @click="markSkipped">高级用户：手动管理计划</router-link>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { trackUsageEvent } from "@/api/usageEvents";
import { getStoredToken } from "@/api/auth";
import { preferenceKey } from "@/utils/coreExperience";

const router = useRouter();
const step = ref(1);
const mode = ref<'ai' | 'import' | 'record'>('import');
const guideKey = preferenceKey(getStoredToken(), 'guide');

function markSkipped() {
  const key = preferenceKey(getStoredToken(), 'welcome-dismissed');
  if (key) localStorage.setItem(key, "1");
}

function choose(value: typeof mode.value) {
  mode.value = value;
  step.value = 2;
}
function connectDevice() {
  step.value = 3;
  markSkipped();
  router.push({ path: '/data-sync', query: { guide: 'continue' } });
}
function finish() {
  markSkipped();
  router.push(mode.value === 'ai' ? '/ai-plan' : mode.value === 'import' ? '/plan-imports' : '/dashboard');
}

function skip() {
  markSkipped();
  router.push("/today");
}

onMounted(() => {
  if (guideKey) {
    try {
      const saved = JSON.parse(localStorage.getItem(guideKey) || 'null');
      if (saved && ['ai', 'import', 'record'].includes(saved.mode) && [1, 2, 3].includes(saved.step)) {
        mode.value = saved.mode; step.value = saved.step;
      }
    } catch { /* Ignore invalid local UI preferences. */ }
  }
  trackUsageEvent("onboarding_viewed");
});
watch([step, mode], () => {
  if (guideKey) localStorage.setItem(guideKey, JSON.stringify({ step: step.value, mode: mode.value }));
});
</script>

<style scoped>
.guide-steps{display:flex;gap:12px;justify-content:center;list-style:none;padding:0;margin:0}.guide-steps li{display:flex;gap:7px;align-items:center;font-size:12px;color:var(--muted)}.guide-steps span{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:var(--surface-muted)}.guide-steps .active{color:var(--primary);font-weight:700}.guide-steps .active span{background:var(--primary);color:white}.guide-steps .done span{border:1px solid var(--primary)}.guide-actions{display:flex;gap:10px;flex-wrap:wrap}.guide-actions :deep(.el-button){margin:0}
.guide-panel{max-width:760px;width:100%;margin:0 auto;padding:28px}.guide-panel p{color:var(--muted);line-height:1.8}.guide-note{font-size:13px}.guide-footer{display:flex;justify-content:center;flex-wrap:wrap;gap:18px;align-items:center;font-size:13px}.guide-footer a{color:var(--muted)}
.welcome-page {
  display: grid;
  gap: 22px;
  max-width: 1120px;
  min-height: calc(100vh - 160px);
  margin: 0 auto;
  padding: 48px 24px;
  align-content: center;
}

.welcome-hero {
  display: grid;
  gap: 10px;
  text-align: center;
}

.welcome-hero p {
  margin: 0;
  color: #1976d2;
  font-weight: 800;
}

.welcome-hero h1 {
  margin: 0;
  color: #172033;
  font-size: 38px;
}

.welcome-hero span {
  color: #667085;
  line-height: 1.7;
}

.welcome-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.welcome-card {
  min-height: 188px;
  padding: 24px;
  border: 1px solid #d8dde3;
  border-radius: 8px;
  background: #ffffff;
  color: #172033;
  text-align: left;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
}

.welcome-card.primary {
  border-color: #1976d2;
  background: #f3f9ff;
}

.welcome-card strong {
  display: block;
  margin-bottom: 12px;
  font-size: 20px;
}

.welcome-card span {
  color: #667085;
  line-height: 1.7;
}

.skip-button {
  justify-self: center;
  border: 0;
  background: transparent;
  color: #667085;
  cursor: pointer;
}

@media (max-width: 768px) {
  .welcome-page {
    padding: 22px 14px;
    min-height:0;
    gap:20px;
    align-content:start;
  }

  .welcome-grid {
    grid-template-columns: 1fr;
  }

  .welcome-hero h1 {
    font-size: 26px;
    line-height:1.4;
  }

  .welcome-card {
    min-height: auto;
    padding:20px;
  }
  .welcome-card strong{font-size:17px;margin-bottom:8px}.welcome-card span{font-size:14px}.welcome-hero span{font-size:14px}.guide-panel{padding:20px}.guide-panel h2{font-size:20px;line-height:1.6}.guide-actions{display:grid;grid-template-columns:1fr}.guide-panel :deep(.el-button){min-height:46px;width:100%;white-space:normal;height:auto;padding:12px}.guide-footer{display:grid;gap:4px;text-align:center}.guide-footer>*{min-height:44px;display:flex;justify-content:center;align-items:center}.guide-steps{gap:8px;justify-content:space-between}.guide-steps li{gap:5px;font-size:11px}
}
</style>
