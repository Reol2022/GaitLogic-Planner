<template><section><div class="page-heading"><div><div class="eyebrow">ACCOUNTABILITY</div><h1>操作审计</h1><p>记录操作者、对象与变更字段，不记录字段原值、密钥或健康详情。</p></div><el-button @click="load" :loading="busy">刷新</el-button></div>
  <div class="card"><el-alert v-if="error" :title="error" type="error" :closable="false"/>
    <div class="mobile-record-list" aria-label="审计记录卡片" v-loading="busy"><MobileRecordCard v-for="item in items" :key="item.id" :title="item.action"><p>{{item.created_at}} UTC</p><dl><div><dt>管理员 ID</dt><dd>{{item.actor_user_id ?? '账号已删除'}}</dd></div><div><dt>对象</dt><dd>{{item.target_type}} #{{item.target_id ?? '—'}}</dd></div></dl><details><summary>查看变更字段（{{item.changed_fields.length}}）</summary><p>{{item.changed_fields.join('、') || '无字段变化'}}</p></details></MobileRecordCard><el-empty v-if="!busy && !items.length" description="暂无操作记录"/></div>
    <el-table class="desktop-record-table" :data="items" v-loading="busy"><el-table-column prop="created_at" label="时间（服务器 UTC）" min-width="200"/><el-table-column prop="actor_user_id" label="管理员 ID" width="120"/><el-table-column prop="action" label="动作" min-width="230"/><el-table-column prop="target_type" label="对象类型" min-width="130"/><el-table-column prop="target_id" label="对象 ID" width="100"/><el-table-column label="字段"><template #default="{row}">{{row.changed_fields.join(', ') || '无字段变化'}}</template></el-table-column></el-table><el-pagination layout="prev,pager,next,total" v-model:current-page="page" :page-size="20" :total="total" @current-change="load" :disabled="busy"/>
  </div></section></template>
<script setup lang="ts">
import {onMounted,ref} from 'vue';import {api,consoleApi,errorText} from './api';
import MobileRecordCard from '@/components/common/MobileRecordCard.vue';
interface AuditEvent{id:number;action:string;created_at:string;actor_user_id:number|null;target_type:string;target_id:number|null;changed_fields:string[]}
const items=ref<AuditEvent[]>([]),page=ref(1),total=ref(0),busy=ref(false),error=ref('');
async function load(){if(busy.value)return;busy.value=true;error.value='';try{const {data}=await api.get(consoleApi+'/audit',{params:{page:page.value,page_size:20}});items.value=data.items;total.value=data.total;}catch(e){items.value=[];error.value=errorText(e);}finally{busy.value=false;}}onMounted(load);
</script>
