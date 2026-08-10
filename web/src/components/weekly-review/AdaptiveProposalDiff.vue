<template>
  <section class="panel proposal-panel">
    <header><div><h2>训练计划调整 Proposal</h2><p>只有你确认后，服务端才会重新校验并写入新计划版本。</p></div><el-tag>{{ proposal.status }}</el-tag></header>
    <el-alert v-for="warning in proposal.proposal.warnings" :key="warning" :title="warning" type="warning" :closable="false" show-icon />
    <article v-for="change in proposal.proposal.changes" :key="change.plan_id" class="change-card">
      <div class="change-title"><strong>{{ change.date }}</strong><el-tag size="small">{{ change.action }}</el-tag></div>
      <div class="diff-grid">
        <div><span>原计划</span><p>{{ change.before.content }}</p><small>{{ distance(change.before.distance_km) }} · {{ change.before.main_type }}</small></div>
        <div class="after"><span>建议计划</span><p>{{ change.after.content }}</p><small>{{ distance(change.after.distance_km) }} · {{ change.after.main_type }}</small></div>
      </div>
      <p><strong>修改原因：</strong>{{ change.reason }}</p>
      <p class="evidence"><strong>规则证据：</strong>{{ change.rule_evidence.join("、") }}</p>
    </article>
    <div v-if="proposal.status === 'pending_approval'" class="actions">
      <el-button @click="$emit('reject')">拒绝并保留原计划</el-button>
      <el-button type="primary" @click="$emit('approve')">确认并创建新计划版本</el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdaptiveProposal } from "@/types/adaptivePlan";
defineProps<{ proposal: AdaptiveProposal }>();
defineEmits<{ approve: []; reject: [] }>();
function distance(value: number | null) { return value === null ? "暂无数据" : `${value.toFixed(1)} km`; }
</script>

<style scoped>
.proposal-panel{padding:18px}.proposal-panel header,.change-title,.actions{display:flex;justify-content:space-between;align-items:center;gap:12px}.proposal-panel h2{margin:0}.proposal-panel header p{margin:6px 0;color:var(--muted)}.proposal-panel :deep(.el-alert){margin-top:10px}.change-card{margin-top:12px;padding:14px;border:1px solid var(--card-border);border-radius:12px}.diff-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}.diff-grid>div{padding:12px;background:var(--surface-muted);border-radius:10px}.diff-grid .after{background:#eef8f4}.diff-grid span,.diff-grid small,.evidence{color:var(--muted)}.actions{justify-content:flex-end;margin-top:16px}@media(max-width:600px){.diff-grid{grid-template-columns:1fr}.actions{align-items:stretch;flex-direction:column-reverse}.actions :deep(.el-button){margin-left:0;width:100%}}
</style>
