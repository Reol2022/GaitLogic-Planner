<template>
  <el-container class="app-shell">
    <el-aside width="232px" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">GL</div>
        <div>
          <div class="brand-name">GaitLogic</div>
          <div class="brand-subtitle">训练计划与日志</div>
        </div>
      </div>

      <el-menu :default-active="route.path" router class="side-menu">
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>Dashboard</span>
        </el-menu-item>
        <el-menu-item index="/cycles">
          <el-icon><Calendar /></el-icon>
          <span>训练周期</span>
        </el-menu-item>
        <el-menu-item index="/blocks">
          <el-icon><Grid /></el-icon>
          <span>训练块</span>
        </el-menu-item>
        <el-menu-item index="/workouts">
          <el-icon><List /></el-icon>
          <span>训练计划</span>
        </el-menu-item>
        <el-menu-item index="/today">
          <el-icon><Timer /></el-icon>
          <span>今日训练</span>
        </el-menu-item>
        <el-menu-item index="/pace-rules">
          <el-icon><Odometer /></el-icon>
          <span>配速规则</span>
        </el-menu-item>
        <el-menu-item index="/excel-import">
          <el-icon><DocumentAdd /></el-icon>
          <span>Excel 导入</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h1>{{ pageTitle }}</h1>
          <p>严肃跑者的训练计划、日志与复盘工作台</p>
        </div>
        <div class="header-user">
          <el-icon><User /></el-icon>
          <span>{{ displayName }}</span>
          <el-button size="small" type="primary" plain :icon="SwitchButton" @click="handleLogout">
            退出
          </el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Calendar,
  DataAnalysis,
  DocumentAdd,
  Grid,
  List,
  Odometer,
  SwitchButton,
  Timer,
  User,
} from "@element-plus/icons-vue";
import { clearStoredToken, getCurrentUser, logoutUser } from "@/api/auth";
import type { UserAccount } from "@/types/models";

const route = useRoute();
const router = useRouter();
const currentUser = ref<UserAccount | null>(null);

const pageTitle = computed(() => String(route.meta.title || "Dashboard"));
const displayName = computed(
  () => currentUser.value?.nickname || currentUser.value?.username || "已登录",
);

async function loadCurrentUser() {
  currentUser.value = await getCurrentUser();
}

async function handleLogout() {
  try {
    await logoutUser();
  } finally {
    clearStoredToken();
    currentUser.value = null;
    router.push("/login");
  }
}

onMounted(() => {
  loadCurrentUser();
});
</script>
