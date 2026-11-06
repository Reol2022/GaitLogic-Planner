<template><div class="login-page"><section class="login-copy"><div class="eyebrow">GAITLOGIC CONTROL</div><h1>管理系统，<br>让训练体验更简单。</h1><p>用户管理 · AI 配置 · 操作审计</p><small>管理身份由服务器验证。普通训练账号无法进入。</small></section>
  <form class="login-card" @submit.prevent="submit"><div class="eyebrow">管理员登录</div><h2>欢迎回来</h2><p>使用已有 GaitLogic 管理员账号。</p><label>用户名<el-input v-model="username" autocomplete="username" required /></label><label>密码<el-input v-model="password" type="password" autocomplete="current-password" required /></label><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-button native-type="submit" type="primary" :loading="busy">进入控制台</el-button><small>本标签页独立保存登录状态，退出后清除。请在可信设备使用。</small></form>
</div></template>
<script setup lang="ts">
import {ref} from 'vue';import {useRouter} from 'vue-router';import {login,errorText} from './api';
const username=ref(''),password=ref(''),error=ref(''),busy=ref(false),router=useRouter();
async function submit(){if(busy.value)return;busy.value=true;error.value='';try{await login(username.value,password.value);password.value='';await router.replace('/');}catch(e){password.value='';error.value=errorText(e);}finally{busy.value=false;}}
</script>
