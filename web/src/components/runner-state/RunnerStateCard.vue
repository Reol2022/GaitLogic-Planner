<template>
  <article class="state-card" :class="`tone-${display.tone}`">
    <div class="state-card__head">
      <div class="state-card__icon"><el-icon><component :is="icon" /></el-icon></div>
      <div>
        <span>{{ title }}</span>
        <h3>{{ display.label }}</h3>
      </div>
    </div>
    <p class="state-card__note">{{ display.note }}</p>
    <dl v-if="details.length" class="state-card__metrics">
      <div v-for="item in details" :key="item.label">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>
    <RunnerStateEvidence
      :evidence="evidence"
      :skipped-signals="skippedSignals"
      :reason-codes="reasonCodes"
      :ruleset-version="rulesetVersion"
      :evidence-coverage="evidenceCoverage"
    />
  </article>
</template>

<script setup lang="ts">
import type { Component } from "vue";
import type { RunnerStateEvidence as RunnerStateEvidenceItem } from "@/types/runnerState";
import type { StateDisplay } from "@/utils/runnerStateDisplay";
import RunnerStateEvidence from "./RunnerStateEvidence.vue";

withDefaults(defineProps<{
  title: string;
  icon: Component;
  display: StateDisplay;
  details?: Array<{ label: string; value: string }>;
  evidence?: RunnerStateEvidenceItem[];
  skippedSignals?: string[];
  reasonCodes?: string[];
  rulesetVersion?: string | null;
  evidenceCoverage?: number | null;
}>(), {
  details: () => [],
  evidence: () => [],
  skippedSignals: () => [],
  reasonCodes: () => [],
  rulesetVersion: null,
  evidenceCoverage: null,
});
</script>

<style scoped>
.state-card { min-width: 0; padding: 16px; border: 1px solid var(--card-border); border-top: 3px solid #8293a4; border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
.state-card.tone-positive { border-top-color: var(--success); }
.state-card.tone-notice { border-top-color: var(--accent); }
.state-card.tone-attention { border-top-color: #b35b46; }
.state-card__head { display: flex; align-items: center; gap: 12px; }
.state-card__icon { display: grid; place-items: center; width: 38px; height: 38px; flex: 0 0 auto; border-radius: 8px; color: #1f4e79; background: var(--blue-soft); font-size: 20px; }
.state-card__head span { color: var(--muted); font-size: 12px; }
h3 { margin: 3px 0 0; overflow-wrap: anywhere; color: #172033; font-size: 17px; line-height: 1.35; }
.state-card__note { min-height: 42px; margin: 12px 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
.state-card__metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; margin: 0; }
.state-card__metrics div { min-width: 0; padding: 9px; border-radius: 5px; background: #f7f9fb; }
dt { color: var(--muted); font-size: 11px; }
dd { margin: 4px 0 0; overflow-wrap: anywhere; color: #344054; font-size: 13px; font-weight: 700; }

@media (max-width: 520px) {
  .state-card { padding: 14px; }
  .state-card__note { min-height: 0; }
}
</style>
