<template>
  <section class="recommendation-card" :class="`tone-${decisionDisplay.tone}`" aria-labelledby="coach-recommendation-title">
    <div class="card-heading">
      <div>
        <span class="eyebrow">确定性规则建议</span>
        <h2 id="coach-recommendation-title">{{ decisionDisplay.label }}</h2>
      </div>
      <span class="risk-label" :class="`tone-${riskDisplay.tone}`">{{ riskDisplay.label }}</span>
    </div>

    <p class="headline">{{ recommendation.headline }}</p>
    <dl class="facts-grid">
      <div>
        <dt>今日计划</dt>
        <dd>{{ coachPlannedStatusDisplay[recommendation.planned_workout_status] }}</dd>
      </div>
      <div>
        <dt>数据质量</dt>
        <dd>{{ coachDataQualityLabel(recommendation.data_quality) }}</dd>
      </div>
    </dl>

    <div class="evidence-block">
      <strong>关键依据</strong>
      <ul v-if="recommendation.key_evidence.length">
        <li v-for="item in recommendation.key_evidence" :key="item">{{ item }}</li>
      </ul>
      <p v-else>暂无可展示的关键依据。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { CoachRiskLevel, CoachTodayRecommendation } from "@/types/coachAgent";
import {
  coachDataQualityLabel,
  coachDecisionDisplay,
  coachPlannedStatusDisplay,
  coachRiskDisplay,
} from "@/utils/coachAgentDisplay";

const props = defineProps<{
  recommendation: CoachTodayRecommendation;
  riskLevel: CoachRiskLevel;
}>();

const decisionDisplay = computed(() => coachDecisionDisplay[props.recommendation.decision]);
const riskDisplay = computed(() => coachRiskDisplay[props.riskLevel]);
</script>

<style scoped>
.recommendation-card { min-width: 0; padding: 20px; border: 1px solid #d8e2ec; border-left: 5px solid #8293a4; border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
.recommendation-card.tone-positive { border-left-color: var(--success); }
.recommendation-card.tone-notice { border-left-color: #d89a2b; }
.recommendation-card.tone-attention { border-left-color: #b5473f; }
.card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.eyebrow { color: #1f4e79; font-size: 12px; font-weight: 700; }
h2 { margin: 4px 0 0; overflow-wrap: anywhere; color: #172033; font-size: 22px; }
.risk-label { flex: 0 0 auto; padding: 6px 9px; border-radius: 999px; background: #eef2f6; color: #475467; font-size: 12px; font-weight: 700; }
.risk-label.tone-positive { background: #eaf6ee; color: #207044; }
.risk-label.tone-notice { background: #fff4dc; color: #8a5b0b; }
.risk-label.tone-attention { background: #fce9e7; color: #9f352e; }
.headline { margin: 16px 0; overflow-wrap: anywhere; color: #344054; font-size: 15px; line-height: 1.7; }
.facts-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 0; }
.facts-grid div { min-width: 0; padding: 11px; border-radius: 7px; background: #f7f9fb; }
dt { color: #667085; font-size: 12px; }
dd { margin: 5px 0 0; overflow-wrap: anywhere; color: #26354a; font-size: 14px; font-weight: 700; }
.evidence-block { margin-top: 16px; }
.evidence-block strong { color: #344054; font-size: 13px; }
.evidence-block ul { display: flex; flex-wrap: wrap; gap: 8px; margin: 9px 0 0; padding: 0; list-style: none; }
.evidence-block li { max-width: 100%; padding: 6px 9px; overflow-wrap: anywhere; border: 1px solid #dce6ef; border-radius: 6px; color: #475467; background: #f8fafc; font-size: 12px; }
.evidence-block p { margin: 8px 0 0; color: #667085; font-size: 13px; }
@media (max-width: 520px) {
  .recommendation-card { padding: 16px; }
  .card-heading { flex-direction: column; }
  .facts-grid { grid-template-columns: 1fr; }
}
</style>
