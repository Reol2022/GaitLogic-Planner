<template><section><div class="page-heading"><div><div class="eyebrow">MODEL OPERATIONS</div><h1>AI 配置</h1><p>配置可审查、发布可确认、历史可回退。不会关闭 Validator 或计划审批。</p></div><el-button @click="load" :disabled="busy">重新加载</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <template v-if="state"><el-alert :title="state.notice" type="info" :closable="false"/>
  <div class="two-columns"><article class="card"><h2>课表生成配置草稿</h2><p>当前来源：{{state.source}} · 密钥{{state.has_api_key?'已配置':'未配置'}}。不展示密钥片段。</p>
    <el-form v-if="form" label-position="top"><el-form-item label="模型 ID"><el-input v-model="form.model_name" maxlength="128" placeholder="输入已确认可用的模型 ID"/></el-form-item>
    <div class="field-grid"><el-form-item v-for="field in fields" :key="field.key" :label="field.label"><el-input-number v-model="form[field.key]" :min="field.min" :max="field.max" :step="field.step || 1"/></el-form-item></div></el-form>
    <p class="muted">只做结构与取值校验，保存不会发起模型请求。连接成功和回答质量需要另外验收。Provider 地址与密钥仍由服务器管理。</p>
    <el-button type="primary" :loading="busy" @click="draft">保存为草稿</el-button>
  </article><article class="card"><h2>配置版本</h2><p>草稿不会生效。点击发布后，经确认才更新数据库配置；已经开始的请求不会被追溯修改。</p><p v-if="!state.initialized" class="muted">尚未初始化配置，请先执行控制台迁移。</p>
    <div v-for="revision in revisions" :key="revision.id" class="revision"><header><b>#{{revision.id}}</b><el-tag>{{revision.status==='DRAFT'?'草稿':revision.status==='SNAPSHOT'?'发布前快照':'已发布版本'}}</el-tag></header><p>{{revision.config_json.model_name}} · {{revision.created_at?.replace('T',' ')}}</p><el-button v-if="revision.status==='DRAFT'" size="small" :disabled="busy" @click="publish(revision)">发布此草稿</el-button><el-button v-else size="small" :disabled="busy" @click="rollback(revision)">基于此版创建恢复草稿</el-button></div>
    <el-empty v-if="!revisions.length" description="还没有配置版本"/>
  </article></div>
  <article class="card"><h2>Coach 与工作流档位 · 只读</h2><p>这些是服务器解析出的执行配置，不代表模型已通过真实 API 可用性测试。环境配置修改后需要按现有方式重启服务。</p><div class="mobile-record-list" aria-label="模型档位卡片"><MobileRecordCard v-for="profile in state.profiles" :key="profile.task" :title="profile.task"><p>档位：{{profile.profile}}</p><p>模型：{{profile.model}}</p><p>Thinking：{{profile.thinking_enabled?'已启用':'未启用'}} · 超时 {{profile.timeout_seconds}} 秒</p></MobileRecordCard></div><el-table class="desktop-record-table" :data="state.profiles"><el-table-column prop="task" label="任务" min-width="220"/><el-table-column prop="profile" label="档位" min-width="150"/><el-table-column prop="model" label="配置模型" min-width="200"/><el-table-column label="Thinking" width="120"><template #default="{row}">{{row.thinking_enabled?'已启用':'未启用'}}</template></el-table-column><el-table-column prop="timeout_seconds" label="超时 / 秒" width="130"/></el-table></article></template>
</section></template>
<script setup lang="ts">
import {onMounted,ref} from 'vue';import {ElMessage,ElMessageBox} from 'element-plus';import {api,consoleApi,errorText} from './api';
import MobileRecordCard from '@/components/common/MobileRecordCard.vue';
interface Plan{model_name:string;timeout_seconds:number;ai_plan_daily_limit:number;ai_plan_cooldown_seconds:number;temperature:number;top_p:number;max_tokens_per_week:number;max_tokens_cap:number}
interface State{config:Plan;fingerprint:string;source:string;notice:string;has_api_key:boolean;initialized:boolean;profiles:{task:string;profile:string;model:string;thinking_enabled:boolean;timeout_seconds:number}[]}
interface Revision{id:number;status:string;created_at:string;config_json:Plan}
const state=ref<State|null>(null),form=ref<Plan|null>(null),revisions=ref<Revision[]>([]),busy=ref(false),error=ref('');
const fields:{key:Exclude<keyof Plan,'model_name'>;label:string;min:number;max:number;step?:number}[]=[{key:'timeout_seconds',label:'请求超时（秒）',min:10,max:600},{key:'ai_plan_daily_limit',label:'每人每日生成上限（0为关闭）',min:0,max:1000},{key:'ai_plan_cooldown_seconds',label:'生成冷却（秒）',min:0,max:86400},{key:'temperature',label:'Temperature',min:0,max:2,step:0.05},{key:'top_p',label:'Top P',min:0.05,max:1,step:0.05},{key:'max_tokens_per_week',label:'每周输出 Token 预算',min:500,max:10000,step:100},{key:'max_tokens_cap',label:'总输出 Token 上限',min:4096,max:128000,step:1000}];
async function refresh(){const [settings,history]=await Promise.all([api.get(consoleApi+'/ai'),api.get(consoleApi+'/ai/revisions')]);state.value=settings.data;form.value={...settings.data.config};revisions.value=history.data;}
async function load(){if(busy.value)return;busy.value=true;error.value='';try{await refresh();}catch(e){state.value=null;error.value=errorText(e);}finally{busy.value=false;}}
async function draft(){if(!state.value||!form.value||busy.value)return;busy.value=true;try{await api.post(consoleApi+'/ai/drafts',{config:form.value,expected_fingerprint:state.value.fingerprint});await refresh();ElMessage.success('草稿已保存，尚未生效');}catch(e){ElMessage.error(errorText(e));}finally{busy.value=false;}}
async function publish(revision:Revision){if(!state.value||busy.value)return;const expected=state.value.fingerprint;
  try{await ElMessageBox.confirm(`确认发布 #${revision.id}？这会影响后续课表生成。模型可用性尚未自动验证。`,'发布配置',{type:'warning',confirmButtonText:'确认发布',cancelButtonText:'取消'});}catch{return;}
  if(busy.value)return;busy.value=true;try{await api.post(`${consoleApi}/ai/revisions/${revision.id}/publish`,{expected_fingerprint:expected});await refresh();ElMessage.success('配置已发布');}catch(e){ElMessage.error(errorText(e));}finally{busy.value=false;}}
async function rollback(revision:Revision){if(busy.value)return;busy.value=true;try{await api.post(`${consoleApi}/ai/revisions/${revision.id}/rollback-draft`);await refresh();ElMessage.success('已创建恢复草稿，仍需明确发布');}catch(e){ElMessage.error(errorText(e));}finally{busy.value=false;}}
onMounted(load);
</script>
