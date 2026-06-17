<template>
  <main class="welcome-page">
    <section class="welcome-hero">
      <p>首次使用</p>
      <h1>开始你的训练计划</h1>
      <span>选择一种开始方式。AI 适合从目标赛事开始，Excel 适合已有计划，手动创建适合高级用户。</span>
    </section>

    <section class="welcome-grid">
      <button type="button" class="welcome-card primary" @click="goAI">
        <strong>AI 帮我制定计划</strong>
        <span>根据当前能力、跑量和比赛目标生成计划草稿。</span>
      </button>
      <button type="button" class="welcome-card" @click="goExcel">
        <strong>导入已有 Excel 计划</strong>
        <span>适合已经有训练计划的跑者。</span>
      </button>
      <button type="button" class="welcome-card" @click="goManual">
        <strong>手动创建训练计划</strong>
        <span>适合希望自行安排训练的高级用户。</span>
      </button>
    </section>

    <button class="skip-button" type="button" @click="skip">暂时跳过</button>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";

import { trackUsageEvent } from "@/api/usageEvents";

const router = useRouter();

function markSkipped() {
  localStorage.setItem("gaitlogic_welcome_skipped", "1");
}

function goAI() {
  trackUsageEvent("onboarding_ai_selected");
  router.push("/ai-plan");
}

function goExcel() {
  trackUsageEvent("onboarding_excel_selected");
  router.push("/excel-import");
}

function goManual() {
  trackUsageEvent("onboarding_manual_selected");
  router.push("/cycles");
}

function skip() {
  markSkipped();
  router.push("/today");
}

onMounted(() => {
  trackUsageEvent("onboarding_viewed");
});
</script>

<style scoped>
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
    padding: 28px 16px;
  }

  .welcome-grid {
    grid-template-columns: 1fr;
  }

  .welcome-hero h1 {
    font-size: 30px;
  }

  .welcome-card {
    min-height: auto;
  }
}
</style>
