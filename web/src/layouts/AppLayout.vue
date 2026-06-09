<template>
  <el-container class="app-shell" :class="{ 'is-collapsed': sidebarCollapsed }">
    <el-aside :width="sidebarCollapsed ? '72px' : '272px'" class="app-sidebar">
      <div class="brand">
        <div v-if="sidebarCollapsed" class="brand-mini">GL</div>
        <div v-else class="brand-lockup"> 
          <div>
            <strong style="font-size:26px;">GaitLogic</strong>
          </div>
        </div>
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
        <el-menu-item index="/ai-plan">
          <el-icon><Odometer /></el-icon>
          <template #title>AI 课表</template>
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
        <el-menu-item index="/pace-calculator">
          <el-icon><Stopwatch /></el-icon>
          <template #title>配速计算器</template>
        </el-menu-item>
        <el-menu-item index="/pace-rules">
          <el-icon><TrendCharts /></el-icon>
          <template #title>配速规则</template>
        </el-menu-item>
        <el-menu-item index="/excel-import">
          <el-icon><DocumentAdd /></el-icon>
          <template #title>Excel 导入</template>
        </el-menu-item>
        <el-menu-item index="/feedback">
          <el-icon><Message /></el-icon>
          <template #title>反馈</template>
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
          <div class="page-heading">
            <h1>{{ pageTitle }}</h1>
            <p>训练计划、执行日志与跑量趋势</p>
          </div>
        </div>
        <div class="header-tools">
          <span class="sync-text">本地训练台</span>
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
  Message,
  Odometer,
  Setting,
  Stopwatch,
  SwitchButton,
  Timer,
  TrendCharts,
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

<style scoped>
.app-shell {
  min-height: 100vh;
  background: #f4f6f8;
}

.app-sidebar {
  overflow: hidden;
  border-right: 1px solid #22272d;
  background: #171a1d;
  transition: width 0.2s ease;
}

.brand {
  display: flex;
  align-items: center;
  height: 72px;
  padding: 0 18px;
  border-bottom: 1px solid #282d33;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #ffffff;
}

.brand-lockup strong {
  display: block;
  font-size: 19px;
  font-weight: 650;
  letter-spacing: 0;
}

.brand-lockup small {
  color: #9aa4af;
  font-size: 12px;
}

.brand-mark,
.brand-mini {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: #1f8fff;
  color: #ffffff;
  font-weight: 750;
}

.brand-mini {
  margin: 0 auto;
}

.side-menu {
  border-right: 0;
  background: transparent;
}

.menu-section {
  padding: 18px 20px 8px;
  color: #737d89;
  font-size: 12px;
  font-weight: 700;
}

:deep(.el-menu) {
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #d8dde3;
  --el-menu-hover-bg-color: #23282f;
  --el-menu-active-color: #ffffff;
}

:deep(.el-menu-item) {
  height: 44px;
  margin: 2px 10px;
  border-radius: 6px;
}

:deep(.el-menu-item.is-active) {
  background: #0b74de;
}

:deep(.el-menu-item .el-icon) {
  color: #20a4ff;
}

:deep(.el-menu-item.is-active .el-icon) {
  color: #ffffff;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 22px;
  border-bottom: 1px solid #d8dde3;
  background: #ffffff;
}

.header-left,
.header-tools {
  display: flex;
  align-items: center;
  gap: 14px;
}

.collapse-button {
  border-color: #c9d1da;
  color: #4b5563;
}

.page-heading h1 {
  margin: 0;
  color: #172033;
  font-size: 20px;
  font-weight: 650;
}

.page-heading p {
  margin: 3px 0 0;
  color: #667085;
  font-size: 12px;
}

.sync-text {
  color: #667085;
  font-size: 12px;
}

.tool-icon {
  color: #111827;
}

.user-avatar {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0b74de, #12b981);
  color: #ffffff;
  font-weight: 700;
}

.app-tabs {
  height: 42px;
  padding: 6px 16px 0;
  border-bottom: 1px solid #dfe4ea;
  background: #ffffff;
}

:deep(.app-tabs .el-tabs__header) {
  margin: 0;
}

:deep(.app-tabs .el-tabs__item) {
  border-radius: 6px 6px 0 0;
}

.app-main {
  padding: 22px;
  background: #f4f6f8;
}

@media (max-width: 860px) {
  .page-heading p,
  .sync-text,
  .tool-icon {
    display: none;
  }

  .app-header {
    padding: 0 14px;
  }
}
</style>
