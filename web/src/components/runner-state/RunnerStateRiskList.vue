<template>
  <section v-if="sortedFlags.length" class="risk-section" aria-labelledby="runner-risk-title">
    <div class="section-heading">
      <div>
        <span>训练管理提示</span>
        <h2 id="runner-risk-title">建议复核的项目</h2>
      </div>
      <el-tag type="warning">{{ sortedFlags.length }} 项</el-tag>
    </div>

    <div class="risk-list">
      <article v-for="flag in sortedFlags" :key="flag.code" class="risk-item" :class="`severity-${flag.severity.toLowerCase()}`">
        <div class="risk-item__head">
          <div>
            <el-tag :type="tagType(flag.severity)" size="small">{{ severityLabels[flag.severity] }}</el-tag>
            <h3>{{ riskTitleLabels[flag.code] || "训练安排提示" }}</h3>
          </div>
          <el-icon><Warning /></el-icon>
        </div>
        <p>{{ flag.message }}</p>
        <div class="risk-action">
          <strong>建议检查项</strong>
          <span>{{ actionLabels[flag.suggested_action_type] || "人工复核" }}</span>
        </div>
        <RunnerStateEvidence :evidence="flag.evidence" :ruleset-version="rulesetVersion" />
      </article>
    </div>

    <div class="risk-links">
      <el-button @click="$router.push('/training-plan')">查看训练计划</el-button>
      <el-button @click="$router.push('/training-calendar')">查看最近训练</el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Warning } from "@element-plus/icons-vue";
import type { RiskSeverity, RunnerStateRiskFlag } from "@/types/runnerState";
import { actionLabels, riskTitleLabels, severityLabels, sortRiskFlags } from "@/utils/runnerStateDisplay";
import RunnerStateEvidence from "./RunnerStateEvidence.vue";

const props = withDefaults(defineProps<{ flags?: RunnerStateRiskFlag[]; rulesetVersion?: string | null }>(), {
  flags: () => [],
  rulesetVersion: null,
});

const sortedFlags = computed(() => sortRiskFlags(props.flags));
const tagType = (severity: RiskSeverity) => severity === "ATTENTION" ? "danger" : severity === "WARNING" ? "warning" : "info";
</script>

<style scoped>
.risk-section { padding: 18px; border: 1px solid #efd8ba; border-radius: var(--card-radius); background: #fffdf9; box-shadow: var(--card-shadow); }
.section-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.section-heading span { color: #9a6516; font-size: 12px; font-weight: 700; }
.section-heading h2 { margin: 4px 0 0; font-size: 19px; }
.risk-list { display: grid; gap: 12px; margin-top: 16px; }
.risk-item { min-width: 0; padding: 14px; border: 1px solid #e5e7eb; border-left: 4px solid #8293a4; border-radius: 6px; background: #fff; }
.risk-item.severity-warning { border-left-color: #d89a2b; }
.risk-item.severity-attention { border-left-color: #b35b46; }
.risk-item__head { display: flex; justify-content: space-between; gap: 12px; }
.risk-item__head > .el-icon { color: #a15c30; font-size: 22px; }
.risk-item h3 { display: inline; margin: 0 0 0 8px; font-size: 15px; }
.risk-item p { margin: 11px 0; color: #475467; line-height: 1.65; }
.risk-action { display: flex; flex-wrap: wrap; gap: 8px; color: #344054; font-size: 13px; }
.risk-action strong { color: var(--muted); }
.risk-links { display: flex; gap: 10px; margin-top: 14px; }

@media (max-width: 520px) {
  .risk-section { padding: 14px; }
  .risk-links { flex-direction: column; }
  .risk-links .el-button { width: 100%; min-height: 44px; margin-left: 0; }
}
</style>
