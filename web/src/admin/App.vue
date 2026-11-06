<template>
  <router-view v-if="route.path==='/login'" />
  <div v-else class="console-shell">
    <aside><a class="brand" href="#/">G<span>GaitLogic<small>管理控制台</small></span></a><div class="nav-label">工作空间</div>
      <nav><router-link v-for="item in items" :key="item.path" :to="item.path" :class="{selected:route.path===item.path}"><span>{{item.icon}}</span>{{item.label}}</router-link></nav>
      <div class="boundary">只管理运行配置与账号<br>不读取个人聊天和健康明细</div>
    </aside>
    <main><header class="console-header"><div>{{route.meta.title || '管理控制台'}}<span class="badge">ADMIN</span></div><div>{{adminUser?.username}} <el-button text @click="signOut">退出</el-button></div></header>
      <div class="console-content"><router-view v-if="adminUser" /><el-result v-else icon="warning" title="管理会话已失效" sub-title="请重新登录；未保存的编辑不会自动提交。"><template #extra><el-button @click="signOut">重新登录</el-button></template></el-result></div>
    </main>
  </div>
</template>
<script setup lang="ts">
import {useRoute,useRouter} from 'vue-router';
import {adminUser,logout} from './api';
const route=useRoute(),router=useRouter();
const items=[{path:'/',label:'运行概览',icon:'◈'},{path:'/users',label:'用户管理',icon:'◎'},{path:'/ai',label:'AI 配置',icon:'◇'},{path:'/audit',label:'操作审计',icon:'≡'}];
function signOut(){logout();router.replace('/login');}
</script>
