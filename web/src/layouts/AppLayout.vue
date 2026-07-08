<template>
  <el-container class="app-shell" :class="{ 'is-collapsed': sidebarCollapsed }">
    <el-aside :width="sidebarCollapsed ? '72px' : '272px'" class="app-sidebar">
      <div class="brand">
        <div v-if="sidebarCollapsed" class="brand-mini" :title="`${APP_NAME} ${APP_VERSION_LABEL}`">GL</div>
        <div v-else class="brand-lockup">
          <strong>GaitLogic</strong>
          <div class="brand-subline">
            <small>Planner</small>
            <AppVersion class="brand-version" />
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
        <div v-if="!sidebarCollapsed" class="menu-section">训练</div>
        <el-menu-item index="/today">
          <el-icon><Timer /></el-icon>
          <template #title>今日训练</template>
        </el-menu-item>
        <el-menu-item index="/training-calendar">
          <el-icon><Calendar /></el-icon>
          <template #title>训练日历</template>
        </el-menu-item>

        <div v-if="!sidebarCollapsed" class="menu-section">计划</div>
        <el-menu-item index="/training-plan">
          <el-icon><List /></el-icon>
          <template #title>训练计划</template>
        </el-menu-item>

        <div v-if="!sidebarCollapsed" class="menu-section">分析</div>
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>训练统计</template>
        </el-menu-item>
        <el-menu-item index="/training-readiness">
          <el-icon><TrendCharts /></el-icon>
          <template #title>负荷与恢复</template>
        </el-menu-item>

        <div v-if="!sidebarCollapsed" class="menu-section">我的</div>
        <el-menu-item index="/todos">
          <el-icon><Bell /></el-icon>
          <template #title>待办中心</template>
        </el-menu-item>
        <el-menu-item v-if="garminSyncVisible" index="/data-sync">
          <el-icon><Connection /></el-icon>
          <template #title>数据同步</template>
        </el-menu-item>
        <el-menu-item index="/data-management">
          <el-icon><FolderOpened /></el-icon>
          <template #title>数据管理</template>
        </el-menu-item>
        <el-menu-item index="/feedback">
          <el-icon><Message /></el-icon>
          <template #title>反馈</template>
        </el-menu-item>
        <el-menu-item index="/my">
          <el-icon><User /></el-icon>
          <template #title>设置</template>
        </el-menu-item>

        <template v-if="isAdmin">
          <div v-if="!sidebarCollapsed" class="menu-section">管理后台</div>
          <el-menu-item index="/admin/ai-settings">
            <el-icon><Setting /></el-icon>
            <template #title>AI 设置</template>
          </el-menu-item>
          <el-menu-item index="/admin/system-settings">
            <el-icon><Setting /></el-icon>
            <template #title>系统设置</template>
          </el-menu-item>
        </template>
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
          <div class="mobile-brand" :title="`${APP_NAME} ${APP_VERSION_LABEL}`">
            <strong>{{ APP_NAME }}</strong>
            <AppVersion compact />
          </div>
          <div class="page-heading">
            <h1>{{ pageTitle }}</h1>
            <p>训练计划、执行日志与跑量趋势</p>
          </div>
        </div>
        <div class="header-tools">
          <span class="sync-text">本地训练台</span>
          <el-button class="tool-icon" text :icon="Upload" @click="router.push('/data-management')" />
          <el-button class="tool-icon" text :icon="Bell" @click="router.push('/todos')" />
          <el-dropdown trigger="click" @command="handleHeaderSettingCommand">
            <el-button class="tool-icon settings-trigger" text :icon="Setting" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="toggle-tabs">
                  {{ tabsVisible ? "关闭导航栏" : "开启导航栏" }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <div class="user-avatar">{{ userInitial }}</div>
          <el-button v-if="currentUser" size="small" plain :icon="SwitchButton" @click="handleLogout">退出</el-button>
          <el-button v-else size="small" type="primary" plain @click="openLoginDialog">登录</el-button>
        </div>
      </el-header>

      <div v-if="tabsVisible" class="app-tabs">
        <el-tabs
          :model-value="activeTab"
          type="card"
          @tab-click="handleTabClick"
          @tab-remove="handleTabRemove"
        >
          <el-tab-pane
            v-for="tab in visitedTabs"
            :key="tab.path"
            :name="tab.path"
            :closable="tab.path !== '/today'"
          >
            <template #label>
              <span class="tab-label" @contextmenu.prevent.stop="openTabContextMenu($event, tab)">
                {{ tab.title }}
              </span>
            </template>
          </el-tab-pane>
        </el-tabs>
      </div>

      <el-main class="app-main" @touchstart.passive="handleMobileTouchStart" @touchend.passive="handleMobileTouchEnd">
        <div v-if="showMobileBackToMy" class="mobile-content-back">
          <button type="button" aria-label="返回我的" @click="goBackToMy">
            <el-icon><ArrowLeft /></el-icon>
          </button>
          <span>返回我的</span>
        </div>
        <router-view />
        <SiteFilingFooter />
      </el-main>
    </el-container>

    <nav class="mobile-bottom-nav" aria-label="移动端导航">
      <router-link v-for="item in mobileNavItems" :key="item.path" :to="item.path" class="mobile-nav-item">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <div
      v-if="tabContextMenu.visible"
      class="tab-context-menu"
      :style="{ left: `${tabContextMenu.x}px`, top: `${tabContextMenu.y}px` }"
      @click.stop
    >
      <button type="button" :disabled="tabContextMenu.tab?.path === '/today'" @click="closeCurrentTab">
        关闭当前
      </button>
      <button type="button" @click="closeOtherTabs">关闭其他</button>
      <button type="button" @click="closeAllTabs">全部关闭</button>
    </div>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { TabsPaneContext } from "element-plus";
import {
  Bell,
  Calendar,
  Connection,
  DataAnalysis,
  ArrowLeft,
  Expand,
  Fold,
  FolderOpened,
  List,
  Message,
  Setting,
  SwitchButton,
  Timer,
  TrendCharts,
  Upload,
  User,
} from "@element-plus/icons-vue";
import { clearStoredToken, getCurrentUser, logoutUser } from "@/api/auth";
import { listDataSyncProviders } from "@/api/dataSync";
import AppVersion from "@/components/common/AppVersion.vue";
import SiteFilingFooter from "@/components/SiteFilingFooter.vue";
import type { UserAccount } from "@/types/models";
import { APP_NAME, APP_VERSION_LABEL } from "@/config/app";
import { requestAuth } from "@/utils/authPrompt";

interface NavTab {
  path: string;
  title: string;
}

const route = useRoute();
const router = useRouter();
const currentUser = ref<UserAccount | null>(null);
const garminSyncVisible = ref(false);
const sidebarCollapsed = ref(false);
const tabsVisible = ref(true);
const visitedTabs = ref<NavTab[]>([{ path: "/today", title: "今日训练" }]);
const tabContextMenu = ref<{
  visible: boolean;
  x: number;
  y: number;
  tab: NavTab | null;
}>({
  visible: false,
  x: 0,
  y: 0,
  tab: null,
});
const mobileNavItems = [
  { path: "/today", label: "今日", icon: Timer },
  { path: "/training-calendar", label: "日历", icon: Calendar },
  { path: "/training-plan", label: "计划", icon: List },
  { path: "/dashboard", label: "分析", icon: DataAnalysis },
  { path: "/my", label: "我的", icon: User },
];

const pageTitle = computed(() => String(route.meta.title || "GaitLogic"));
const displayName = computed(() => currentUser.value?.nickname || currentUser.value?.username || "访客");
const userInitial = computed(() => displayName.value.slice(0, 1).toUpperCase());
const activeTab = computed(() => route.path);
const isAdmin = computed(() => currentUser.value?.role === "admin");
const showMobileBackToMy = computed(() => route.query.from === "/my" && route.path !== "/my");
const mobileSwipeStart = ref<{ x: number; y: number; time: number } | null>(null);

function addVisitedTab() {
  if (route.meta.public) return;
  const path = route.path;
  const title = pageTitle.value;
  if (path === "/" || !route.name || title === "GaitLogic") return;
  if (visitedTabs.value.some((tab) => tab.path === path)) return;
  visitedTabs.value.push({ path, title });
}

function handleTabClick(tab: TabsPaneContext) {
  const path = String(tab.props.name || "/");
  if (path !== route.path) router.push(path);
}

function handleTabRemove(name: string | number) {
  const path = String(name);
  if (path === "/today") return;
  const index = visitedTabs.value.findIndex((tab) => tab.path === path);
  if (index < 0) return;
  visitedTabs.value.splice(index, 1);
  if (route.path === path) {
    const nextTab = visitedTabs.value[index - 1] || visitedTabs.value[0];
    router.push(nextTab.path);
  }
}

function homeTab() {
  return visitedTabs.value.find((tab) => tab.path === "/today") || { path: "/today", title: "今日训练" };
}

function openTabContextMenu(event: MouseEvent, tab: NavTab) {
  tabContextMenu.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    tab,
  };
}

function closeTabContextMenu() {
  tabContextMenu.value.visible = false;
}

function closeCurrentTab() {
  const tab = tabContextMenu.value.tab;
  if (!tab || tab.path === "/today") return;
  handleTabRemove(tab.path);
  closeTabContextMenu();
}

function closeOtherTabs() {
  const tab = tabContextMenu.value.tab;
  if (!tab) return;
  const home = homeTab();
  visitedTabs.value = tab.path === "/today" ? [home] : [home, tab];
  if (route.path !== tab.path) router.push(tab.path);
  closeTabContextMenu();
}

function closeAllTabs() {
  const home = homeTab();
  visitedTabs.value = [home];
  if (route.path !== "/today") router.push("/today");
  closeTabContextMenu();
}

function handleHeaderSettingCommand(command: string | number) {
  if (command === "toggle-tabs") {
    tabsVisible.value = !tabsVisible.value;
    closeTabContextMenu();
  }
}

function goBackToMy() {
  router.push("/my");
}

function handleMobileTouchStart(event: TouchEvent) {
  if (!showMobileBackToMy.value || window.innerWidth > 768) return;
  const touch = event.touches[0];
  if (!touch) return;
  mobileSwipeStart.value = {
    x: touch.clientX,
    y: touch.clientY,
    time: Date.now(),
  };
}

function handleMobileTouchEnd(event: TouchEvent) {
  const start = mobileSwipeStart.value;
  mobileSwipeStart.value = null;
  if (!start || !showMobileBackToMy.value || window.innerWidth > 768) return;
  const touch = event.changedTouches[0];
  if (!touch) return;

  const deltaX = touch.clientX - start.x;
  const deltaY = Math.abs(touch.clientY - start.y);
  const elapsed = Date.now() - start.time;
  if (start.x <= 90 && deltaX > 70 && deltaY < 55 && elapsed < 800) {
    goBackToMy();
  }
}

function openLoginDialog() {
  requestAuth(route.fullPath);
}

async function loadCurrentUser() {
  try {
    currentUser.value = await getCurrentUser();
    await loadGarminFeatureVisibility();
  } catch {
    currentUser.value = null;
    garminSyncVisible.value = false;
  }
}

async function loadGarminFeatureVisibility() {
  try {
    await listDataSyncProviders(true);
    garminSyncVisible.value = true;
  } catch {
    garminSyncVisible.value = false;
  }
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
  window.addEventListener("click", closeTabContextMenu);
  window.addEventListener("scroll", closeTabContextMenu, true);
});

onBeforeUnmount(() => {
  window.removeEventListener("click", closeTabContextMenu);
  window.removeEventListener("scroll", closeTabContextMenu, true);
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
  display: grid;
  width: max-content;
  color: #ffffff;
}

.brand-lockup strong {
  font-size: 26px;
  font-weight: 650;
  letter-spacing: 0;
}

.brand-lockup small {
  color: #9aa4af;
  font-size: 12px;
}

.brand-subline {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
}

.brand-version {
  color: #8f9aa6;
}

.brand-mini {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  margin: 0 auto;
  border-radius: 8px;
  background: #1f8fff;
  color: #ffffff;
  font-weight: 750;
}

.side-menu {
  border-right: 0;
  background: transparent;
}

.menu-section {
  padding: 16px 20px 7px;
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

:deep(.el-sub-menu .el-sub-menu__title) {
  height: 44px;
  margin: 2px 10px;
  border-radius: 6px;
  color: #d8dde3;
}

:deep(.el-sub-menu .el-sub-menu__title:hover) {
  background: #23282f;
}

:deep(.el-sub-menu .el-menu-item) {
  height: 40px;
  margin-left: 22px;
}

:deep(.el-menu-item.is-active) {
  background: #0b74de;
}

:deep(.el-menu-item .el-icon) {
  color: #20a4ff;
}

:deep(.el-sub-menu .el-icon) {
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

.mobile-brand {
  display: none;
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
  height: 40px;
  padding: 0 16px;
  border-bottom: 1px solid #dfe4ea;
  background: #ffffff;
}

:deep(.app-tabs .el-tabs__header) {
  margin: 0;
}

:deep(.app-tabs .el-tabs__item) {
  height: 39px;
  border-radius: 0;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  height: 100%;
}

.app-main {
  padding: 22px;
  background: #f4f6f8;
}

.mobile-bottom-nav {
  display: none;
}

.mobile-content-back {
  display: none;
}

.tab-context-menu {
  position: fixed;
  z-index: 3000;
  display: grid;
  min-width: 128px;
  padding: 6px;
  border: 1px solid #d8dde3;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
}

.tab-context-menu button {
  height: 34px;
  padding: 0 10px;
  border: 0;
  border-radius: 4px;
  color: #172033;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.tab-context-menu button:hover {
  background: #f2f6fb;
  color: #1976d2;
}

.tab-context-menu button:disabled {
  color: #a0a8b1;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .app-sidebar {
    display: none;
  }

  .page-heading,
  .sync-text,
  .tool-icon:not(.settings-trigger) {
    display: none;
  }

  .mobile-brand {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: center;
    gap: 1px;
    min-width: 0;
    padding-top: 5px;
    color: #172033;
  }

  .mobile-brand strong {
    font-size: 17px;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: 0;
    white-space: nowrap;
  }

  .mobile-brand :deep(.app-version) {
    font-size: 10px;
    line-height: 1.1;
    opacity: 0.66;
  }

  .app-header {
    height: 64px;
    min-height: 64px;
    padding: 12px 14px 8px;
  }

  .header-left,
  .header-tools {
    gap: 10px;
  }

  .app-tabs {
    overflow-x: auto;
    height: 40px;
    padding: 0 10px;
  }

  :deep(.app-tabs .el-tabs__nav-wrap) {
    overflow: visible;
  }

  :deep(.app-tabs .el-tabs__nav-scroll) {
    overflow-x: auto;
  }

  .app-main {
    padding: 0 0 70px;
  }

  .app-tabs {
    display: none;
  }

  .collapse-button {
    display: none;
  }

  .mobile-bottom-nav {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 2200;
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    height: 62px;
    border-top: 1px solid #d8dde3;
    background: #ffffff;
    box-shadow: 0 -4px 18px rgba(15, 23, 42, 0.1);
  }

  .mobile-nav-item {
    display: grid;
    place-items: center;
    align-content: center;
    gap: 3px;
    min-width: 0;
    color: #667085;
    font-size: 12px;
    text-decoration: none;
  }

  .mobile-nav-item .el-icon {
    font-size: 20px;
  }

  .mobile-nav-item.router-link-active {
    color: #1976d2;
    font-weight: 700;
  }

  .mobile-content-back {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px 0;
    color: #172033;
    font-size: 14px;
    font-weight: 650;
  }

  .mobile-content-back button {
    display: inline-grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border: 1px solid #d8dde3;
    border-radius: 50%;
    background: #ffffff;
    color: #172033;
    cursor: pointer;
  }
}

@media (max-width: 520px) {
  .header-left {
    min-width: 0;
  }

  .header-tools {
    flex: 0 0 auto;
    justify-content: flex-end;
  }
}
</style>
