<template>
  <el-container class="app-shell" :class="{ 'is-collapsed': sidebarCollapsed }">
    <el-aside :width="sidebarCollapsed ? '72px' : '272px'" class="app-sidebar">
      <div class="brand">
        <div v-if="sidebarCollapsed" class="brand-mini">GL</div>
        <div v-else class="brand-name">GaitLogic</div>
      </div>

      <el-menu
        :collapse="sidebarCollapsed"
        :collapse-transition="false"
        :default-active="route.path"
        router
        class="side-menu"
      >
        <div v-if="!sidebarCollapsed" class="menu-section">总览</div>
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>Dashboard</template>
        </el-menu-item>
        <el-menu-item index="/today">
          <el-icon><Timer /></el-icon>
          <template #title>今日训练</template>
        </el-menu-item>

        <div v-if="!sidebarCollapsed" class="menu-section">训练管理</div>
        <el-menu-item index="/cycles">
          <el-icon><Calendar /></el-icon>
          <template #title>训练周期</template>
        </el-menu-item>
        <el-menu-item index="/blocks">
          <el-icon><Grid /></el-icon>
          <template #title>训练块</template>
        </el-menu-item>
        <el-menu-item index="/workouts">
          <el-icon><List /></el-icon>
          <template #title>训练计划</template>
        </el-menu-item>

        <div v-if="!sidebarCollapsed" class="menu-section">工具</div>
        <el-menu-item index="/pace-rules">
          <el-icon><Odometer /></el-icon>
          <template #title>配速规则</template>
        </el-menu-item>
        <el-menu-item index="/excel-import">
          <el-icon><DocumentAdd /></el-icon>
          <template #title>Excel 导入</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <el-button
            class="collapse-button"
            circle
            :icon="sidebarCollapsed ? Expand : Fold"
            @click="sidebarCollapsed = !sidebarCollapsed"
          />
          <div>
            <h1>{{ pageTitle }}</h1>
            <p>训练计划、执行日志与跑量趋势</p>
          </div>
        </div>
        <div class="header-tools">
          <span class="sync-text">已同步</span>
          <el-button class="tool-icon" text :icon="Upload" />
          <el-button class="tool-icon" text :icon="Bell" />
          <el-button class="tool-icon" text :icon="Setting" />
          <div class="user-avatar">{{ userInitial }}</div>
          <el-button size="small" plain :icon="SwitchButton" @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <div class="app-tabs">
        <el-tabs
          :model-value="activeTab"
          type="card"
          @tab-click="handleTabClick"
          @tab-remove="handleTabRemove"
        >
          <el-tab-pane
            v-for="tab in visitedTabs"
            :key="tab.path"
            :label="tab.title"
            :name="tab.path"
            :closable="tab.path !== '/'"
          />
        </el-tabs>
      </div>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { TabsPaneContext } from "element-plus";
import {
  Bell,
  Calendar,
  DataAnalysis,
  DocumentAdd,
  Expand,
  Fold,
  Grid,
  List,
  Odometer,
  Setting,
  SwitchButton,
  Timer,
  Upload,
} from "@element-plus/icons-vue";
import { clearStoredToken, getCurrentUser, logoutUser } from "@/api/auth";
import type { UserAccount } from "@/types/models";

interface NavTab {
  path: string;
  title: string;
}

const route = useRoute();
const router = useRouter();
const currentUser = ref<UserAccount | null>(null);
const sidebarCollapsed = ref(false);
const visitedTabs = ref<NavTab[]>([{ path: "/", title: "Dashboard" }]);

const pageTitle = computed(() => String(route.meta.title || "Dashboard"));
const displayName = computed(
  () => currentUser.value?.nickname || currentUser.value?.username || "已登录",
);
const userInitial = computed(() => displayName.value.slice(0, 1).toUpperCase());
const activeTab = computed(() => route.path);

function addVisitedTab() {
  if (route.meta.public) return;
  const path = route.path;
  if (visitedTabs.value.some((tab) => tab.path === path)) return;
  visitedTabs.value.push({ path, title: pageTitle.value });
}

function handleTabClick(tab: TabsPaneContext) {
  const path = String(tab.props.name || "/");
  if (path !== route.path) router.push(path);
}

function handleTabRemove(name: string | number) {
  const path = String(name);
  if (path === "/") return;
  const index = visitedTabs.value.findIndex((tab) => tab.path === path);
  if (index < 0) return;
  visitedTabs.value.splice(index, 1);
  if (route.path === path) {
    const nextTab = visitedTabs.value[index - 1] || visitedTabs.value[0];
    router.push(nextTab.path);
  }
}

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

watch(() => route.fullPath, addVisitedTab, { immediate: true });

onMounted(() => {
  loadCurrentUser();
});
</script>
