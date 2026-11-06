<template>
  <el-container class="app-shell" :class="{ 'is-collapsed': sidebarCollapsed, 'is-coach-route': route.path === '/coach', 'has-mobile-back': showMobileBackToMy }">
    <el-aside :width="sidebarCollapsed ? '72px' : '280px'" class="app-sidebar">
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

      <SidebarNavigation :collapsed="sidebarCollapsed" :admin="isAdmin" :devices="garminSyncVisible" :preferences="sidebarPreferences" :can-configure="!!currentUser" @customize="menuSettingsOpen=true" />
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <el-button
            class="collapse-button"
            circle
            :icon="sidebarCollapsed ? Expand : Fold"
            :aria-label="sidebarCollapsed ? '展开侧边导航' : '收起侧边导航'"
            @click="sidebarCollapsed = !sidebarCollapsed"
          />
          <div class="mobile-brand" :title="`${APP_NAME} ${APP_VERSION_LABEL}`">
            <strong>{{ APP_NAME }}</strong>
            <AppVersion compact />
          </div>
          <div class="page-heading">
            <h1>{{ pageTitle }}</h1>
            <p>安排计划 · 执行训练 · 复盘调整</p>
          </div>
        </div>
        <div class="header-tools">
          <router-link v-if="garminSyncVisible" class="sync-text" to="/data-sync">设备与同步</router-link>
          <el-button class="tool-icon" text :icon="Upload" @click="router.push('/data-management')" />
          <el-button class="tool-icon" text :icon="Bell" @click="router.push('/todos')" />
          <el-dropdown trigger="click" @command="handleHeaderSettingCommand">
            <el-button class="tool-icon settings-trigger" text :icon="Setting" aria-label="打开设置菜单" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="currentUser" command="customize-menu">自定义菜单</el-dropdown-item>
                <el-dropdown-item v-if="isAdmin" command="admin-console">管理控制台</el-dropdown-item>
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
        <router-view v-slot="{ Component }">
          <KeepAlive>
            <component :is="Component" :key="route.path" />
          </KeepAlive>
        </router-view>
        <SiteFilingFooter />
      </el-main>
    </el-container>

    <nav class="mobile-bottom-nav" aria-label="移动端导航" :style="{gridTemplateColumns:`repeat(${mobileNavItems.length+1}, minmax(0,1fr))`}">
      <router-link v-for="item in mobileNavItems" :key="item.path" :to="item.path" class="mobile-nav-item" :class="{ 'is-section-active': mobileActivePath === item.path }" :aria-current="mobileActivePath === item.path ? 'page' : undefined" :title="item.label">
        <el-icon><component :is="mobileIcons[item.icon || 'home']" /></el-icon>
        <span>{{ item.label }}</span>
      </router-link>
      <button type="button" class="mobile-nav-item" :class="{'is-section-active':!mobileActivePath}" aria-label="打开更多功能" :aria-expanded="mobileMenuOpen" @click="mobileMenuOpen=true"><el-icon><MoreFilled /></el-icon><span>更多</span></button>
    </nav>

    <MobileNavigationDrawer v-model="mobileMenuOpen" :preferences="sidebarPreferences" :admin="isAdmin" :devices="garminSyncVisible" @customize="menuSettingsOpen=true" />
    <SidebarPreferencesDialog v-model="menuSettingsOpen" :preferences="sidebarPreferences" :admin="isAdmin" :devices="garminSyncVisible" @save="saveMenuSettings" />

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
  ChatDotRound,
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
  House,
  MoreFilled,
} from "@element-plus/icons-vue";
import { clearStoredToken, getCurrentUser, logoutUser } from "@/api/auth";
import { listDataSyncProviders } from "@/api/dataSync";
import AppVersion from "@/components/common/AppVersion.vue";
import SiteFilingFooter from "@/components/SiteFilingFooter.vue";
import SidebarNavigation from "@/components/common/SidebarNavigation.vue";
import SidebarPreferencesDialog from "@/components/common/SidebarPreferencesDialog.vue";
import MobileNavigationDrawer from '@/components/common/MobileNavigationDrawer.vue';
import {ElMessage} from 'element-plus';
import {configuredMobileNavigation,defaultSidebarPreferences,loadSidebarPreferences,normalizeSidebarPreferences,saveSidebarPreferences,sidebarPreferenceKey,type SidebarPreferences} from '@/utils/sidebarPreferences';
import {sidebarGroups,sidebarSelection} from '@/utils/sidebarNavigation';
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
const sidebarPreferences=ref(defaultSidebarPreferences());
const menuSettingsOpen=ref(false);
const mobileMenuOpen=ref(false);
watch(()=>currentUser.value?.id,()=>{
  menuSettingsOpen.value=false;
  mobileMenuOpen.value=false;
  sidebarPreferences.value=loadSidebarPreferences(currentUser.value?.id ?? null);
});
function saveMenuSettings(value:SidebarPreferences){
  if(!currentUser.value)return;
  sidebarPreferences.value=normalizeSidebarPreferences(value);
  const saved=saveSidebarPreferences(currentUser.value.id,sidebarPreferences.value);
  menuSettingsOpen.value=false;
  if(saved)ElMessage.success('菜单设置已保存');
  else ElMessage.warning('浏览器不允许保存设置，本次已生效，刷新后可能恢复默认');
}
function syncMenuSettings(event:StorageEvent){
  if(event.key===sidebarPreferenceKey(currentUser.value?.id ?? null) || event.key===null){
    sidebarPreferences.value=loadSidebarPreferences(currentUser.value?.id ?? null);
    menuSettingsOpen.value=false;
  }
}
const tabsVisible = ref(false);
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
const mobileIcons={home:House,calendar:Calendar,bell:Bell,chat:ChatDotRound,activity:TrendCharts,recovery:Timer,plan:List,device:Connection,user:User,settings:Setting} as Record<string,typeof House>;
const mobileNavItems=computed(()=>configuredMobileNavigation(isAdmin.value,garminSyncVisible.value,sidebarPreferences.value));

const pageTitle = computed(() => String(route.meta.title || "GaitLogic"));
const primaryNavPath = computed(() => {
  const path = route.path;
  if (path.startsWith('/admin') || path === '/today' || path === '/coach') return path;
  if (['/training-plan', '/training-calendar', '/cycles', '/blocks', '/workouts', '/ai-plan', '/plan-imports'].some(p => path === p || path.startsWith(p + '/'))) return '/training-plan';
  if (['/dashboard', '/weekly-review', '/adaptive-weekly-review', '/runner-state', '/training-readiness'].includes(path)) return '/dashboard';
  return '/my';
});
const displayName = computed(() => currentUser.value?.nickname || currentUser.value?.username || "访客");
const userInitial = computed(() => displayName.value.slice(0, 1).toUpperCase());
const activeTab = computed(() => route.path);
const isAdmin = computed(() => currentUser.value?.role === "admin");
const mobileActivePath=computed(()=>{
  const exact=sidebarSelection(route.path,sidebarGroups(isAdmin.value,garminSyncVisible.value)).activePath;
  if(mobileNavItems.value.some(item=>item.path===exact))return exact;
  return mobileNavItems.value.some(item=>item.path===primaryNavPath.value)?primaryNavPath.value:null;
});
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
  if(command==='customize-menu' && currentUser.value){menuSettingsOpen.value=true;return;}
  if(command==='admin-console' && isAdmin.value){window.location.assign('/admin.html#/');return;}
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
  // Leave horizontal controls and text editing to the component itself.
  const target=event.target;
  if(touch.clientX>24 || (target instanceof Element && target.closest('input,textarea,select,button,a,[role="button"],.el-table,.el-segmented,.message-list'))){mobileSwipeStart.value=null;return;}
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
  if (start.x <= 24 && deltaX > 70 && deltaY < 55 && elapsed < 800) {
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
  window.addEventListener('storage',syncMenuSettings);
  window.addEventListener("click", closeTabContextMenu);
  window.addEventListener("scroll", closeTabContextMenu, true);
});

onBeforeUnmount(() => {
  window.removeEventListener('storage',syncMenuSettings);
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
  position: sticky;
  top: 0;
  align-self: flex-start;
  height: 100dvh;
  overflow: hidden;
  border-right: 1px solid #303030;
  background: #1a1a1a;
  transition: width 0.2s ease;
}

.brand {
  display: flex;
  align-items: center;
  height: 100px;
  padding: 0 24px;
  border-bottom: 0;
}

.brand-lockup {
  display: grid;
  width: max-content;
  color: #ffffff;
}

.brand-lockup strong {
  font-size: 34px;
  font-weight: 500;
  letter-spacing: -1.4px;
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
  background: transparent;
  color: #ffffff;
  font-weight: 750;
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
    position: static;
    height: auto;
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
    min-height: 62px;
    padding-bottom: env(safe-area-inset-bottom, 0px);
    border-top: 1px solid #d8dde3;
    background: #ffffff;
    box-shadow: 0 -4px 18px rgba(15, 23, 42, 0.1);
  }

  .mobile-nav-item {
    border:0;
    background:transparent;
    padding:6px 4px;
    cursor:pointer;
    font-family:inherit;
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
  .mobile-nav-item span{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .mobile-nav-item:focus-visible{outline:2px solid #1686ce;outline-offset:-2px}

  .mobile-nav-item.is-section-active {
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
