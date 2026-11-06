<template><section><div class="page-heading"><div><div class="eyebrow">WORKSPACE</div><h1>运行概览</h1><p>只展示聚合状态，保持管理与跑者隐私之间的边界。</p></div><el-button @click="load" :loading="busy">刷新</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <div class="stats-grid"><article class="card"><small>注册账号</small><strong>{{data?.users_total ?? '—'}}</strong><p>全部账号累计</p></article><article class="card"><small>有效账号</small><strong>{{data?.users_active ?? '—'}}</strong><p>当前未停用</p></article><article class="card"><small>进行中的同步</small><strong>{{data ? (data.sync_jobs.queued || 0)+(data.sync_jobs.running || 0) : '—'}}</strong><p>排队与运行中的任务</p></article></div>
  <div class="two-columns"><article class="card"><h2>从这里开始</h2><router-link class="shortcut" to="/ai"><b>AI 配置 →</b><span>先保存草稿，再明确发布；回滚也需要确认。</span></router-link><router-link class="shortcut" to="/users"><b>用户管理 →</b><span>搜索账号、调整角色与状态。</span></router-link><router-link class="shortcut" to="/audit"><b>操作审计 →</b><span>查看谁修改了哪些字段，不保存字段原值。</span></router-link></article>
  <article class="card"><h2>同步任务状态</h2><p>累计任务数，不代表当前故障率或同步数据完整度。</p><div v-for="(count,status) in data?.sync_jobs" :key="status" class="status-row"><span>{{status}}</span><b>{{count}}</b></div><el-empty v-if="data && !Object.keys(data.sync_jobs).length" description="暂无同步任务"/></article></div>
</section></template>
<script setup lang="ts">
import {ref,onMounted} from 'vue';import {api,consoleApi,errorText} from './api';
const data=ref<{users_total:number;users_active:number;sync_jobs:Record<string,number>}|null>(null),error=ref(''),busy=ref(false);
async function load(){if(busy.value)return;busy.value=true;error.value='';try{data.value=(await api.get(consoleApi+'/overview')).data;}catch(e){data.value=null;error.value=errorText(e);}finally{busy.value=false;}}onMounted(load);
</script>
