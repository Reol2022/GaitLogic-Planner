<template>
  <section class="panel facts-panel">
    <header><div><h2>本周确定性事实</h2><span>{{ facts.period.week_start }} 至 {{ facts.period.week_end }}</span></div><el-tag>{{ facts.data_quality.level }}</el-tag></header>
    <div class="metrics">
      <div><span>计划跑量</span><strong>{{ distance(facts.planned.planned_distance_km) }}</strong></div>
      <div><span>实际跑量</span><strong>{{ distance(facts.completed.actual_distance_km) }}</strong></div>
      <div><span>训练完成</span><strong>{{ facts.completed.completed_running_session_count }}/{{ facts.planned.planned_running_session_count }}</strong></div>
      <div><span>部分完成</span><strong>{{ facts.completed.partial_session_count }}</strong></div>
      <div><span>未完成</span><strong>{{ facts.completed.missed_session_count }}</strong></div>
      <div><span>临时加练</span><strong>{{ facts.completed.extra_session_count }}</strong></div>
    </div>
    <div v-if="facts.classification.domain_readiness?.length" class="readiness" aria-label="Decision readiness">
      <h3>分析准备度</h3>
      <el-tag v-for="item in facts.classification.domain_readiness" :key="item.domain" :type="tagType(item.readiness)" effect="plain">
        {{ domainLabel(item.domain) }}：{{ readinessLabel(item.readiness) }}
      </el-tag>
    </div>
    <div v-if="facts.deviations.length" class="deviations">
      <h3>计划与实际偏差</h3>
      <ul><li v-for="item in facts.deviations" :key="`${item.date}-${item.deviation_type}`"><strong>{{ item.date }}</strong> {{ item.deviation_type }}（{{ item.severity }}）</li></ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { WeeklyFacts } from "@/types/adaptivePlan";
defineProps<{ facts: WeeklyFacts }>();
function distance(value: number | null) { return value === null ? "暂无数据" : `${value.toFixed(1)} km`; }
function readinessLabel(value: string) { return ({ READY: "可分析", PARTIAL: "部分数据", BLOCKED: "数据不足", NOT_APPLICABLE: "不适用" } as Record<string, string>)[value] || value; }
function tagType(value: string) { return ({ READY: "success", PARTIAL: "warning", BLOCKED: "danger", NOT_APPLICABLE: "info" } as Record<string, "success" | "warning" | "danger" | "info">)[value] || "info"; }
function domainLabel(value: string) { return ({ plan_execution: "训练执行", training_volume: "训练负荷", training_frequency: "训练频率", key_session_completion: "关键课", intensity_distribution: "强度分布", long_run: "长距离", recovery: "恢复状态", subjective_fatigue: "主观疲劳", training_phase: "训练阶段" } as Record<string, string>)[value] || value; }
</script>

<style scoped>
.facts-panel{padding:18px}.facts-panel header{display:flex;justify-content:space-between;gap:12px}.facts-panel h2{margin:0}.facts-panel header span{color:var(--muted);font-size:12px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:16px}.metrics div{padding:12px;background:var(--surface-muted);border-radius:10px}.metrics span{display:block;color:var(--muted);font-size:12px}.metrics strong{display:block;margin-top:6px}.deviations{margin-top:16px}.deviations ul{line-height:1.8;padding-left:20px}@media(max-width:600px){.metrics{grid-template-columns:repeat(2,1fr)}}
</style>
