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
</script>

<style scoped>
.facts-panel{padding:18px}.facts-panel header{display:flex;justify-content:space-between;gap:12px}.facts-panel h2{margin:0}.facts-panel header span{color:var(--muted);font-size:12px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:16px}.metrics div{padding:12px;background:var(--surface-muted);border-radius:10px}.metrics span{display:block;color:var(--muted);font-size:12px}.metrics strong{display:block;margin-top:6px}.deviations{margin-top:16px}.deviations ul{line-height:1.8;padding-left:20px}@media(max-width:600px){.metrics{grid-template-columns:repeat(2,1fr)}}
</style>
