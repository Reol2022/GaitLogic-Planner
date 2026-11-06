<template>
  <section class="panel recent-activities" v-loading="loading" aria-label="最近设备活动">
    <header><div><h2>最近同步的实际活动</h2><p>最多展示最近 12 条设备活动，不代表完整时间段或所有手动日志。</p></div><el-button :loading="loading" @click="load">刷新</el-button></header>
    <el-alert v-if="error" :title="error" type="info" :closable="false" />
    <article v-for="item in activities" :key="item.id">
      <div><strong>{{ item.activity_date }} · {{ item.activity_name || '跑步活动' }}</strong><p>{{ distance(item.distance_m) }} · 来源 {{item.provider}} · {{ statusLabel(item.processing_status) }}</p><small>{{ item.planned_workout_id ? '已关联计划，实际类型请以活动及关联结果为准' : '未关联计划，不直接认定为漏练或计划外训练' }}</small></div>
      <router-link v-if="item.planned_workout_id" :to="`/workouts/${item.planned_workout_id}/log`">查看记录</router-link>
      <router-link v-else to="/data-sync">查看关联</router-link>
    </article>
    <p v-if="!loading && !error && !activities.length">还没有同步活动。可以连接设备，或从上方入口导入实际训练记录。</p>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { listSyncedActivities } from '@/api/dataSync';
import type { ExternalActivityRead } from '@/types/models';
import { statusLabel } from '@/utils/statusLabels';
const activities = ref<ExternalActivityRead[]>([]);
const loading = ref(false);
const error = ref('');
async function load() {
  if (loading.value) return;
  loading.value = true; error.value = '';
  try { activities.value = (await listSyncedActivities()).activities; }
  catch { error.value = '设备活动暂不可用或尚未开放。你仍可查看已有周期统计、手动日志或导入记录。'; }
  finally { loading.value = false; }
}
function distance(value?: number | string | null) { return value == null ? '距离缺失' : `${(Number(value) / 1000).toFixed(2)} km`; }
onMounted(load);
</script>
<style scoped>
.recent-activities{padding:20px}.recent-activities header,.recent-activities article{display:flex;gap:16px;justify-content:space-between;align-items:center}.recent-activities h2{margin:0;font-size:18px}.recent-activities p{color:var(--muted);font-size:13px;margin:7px 0}.recent-activities article{border-top:1px solid var(--line-soft);padding:14px 0}.recent-activities article:first-of-type{margin-top:12px}.recent-activities small{color:var(--muted)}.recent-activities a{color:var(--primary);white-space:nowrap}@media(max-width:640px){.recent-activities article{align-items:flex-start;flex-direction:column}}
</style>
