<template>
  <div class="sidebar-navigation-shell">
  <nav class="sidebar-navigation" aria-label="主侧边导航">
    <el-menu ref="menu" class="sidebar-menu" :collapse="collapsed" :collapse-transition="false" :default-active="selection.activePath" router>
      <el-menu-item v-for="item in configured.shortcuts" :key="item.path" :index="item.path" class="sidebar-shortcut">
        <el-icon><component :is="icons[item.icon!]"/></el-icon><template #title><span>{{item.label}}</span></template>
      </el-menu-item>
      <el-menu-item-group class="sidebar-section">
        <el-sub-menu v-for="group in groups" :key="group.id" :index="group.id" popper-class="gaitlogic-sidebar-flyout">
          <template #title><el-icon><component :is="icons[group.icon]"/></el-icon><span>{{group.label}}</span></template>
          <template v-for="item in group.items" :key="item.path">
            <li v-if="item.external" class="sidebar-external" role="none"><a :href="item.path" role="menuitem">{{item.label}}</a></li>
            <el-menu-item v-else :index="item.path">{{item.label}}</el-menu-item>
          </template>
        </el-sub-menu>
      </el-menu-item-group>
    </el-menu>
  </nav>
  <button class="customize-sidebar" type="button" :disabled="!canConfigure" aria-label="自定义菜单" @click="emit('customize')"><el-icon><Setting /></el-icon><span v-if="!collapsed">自定义菜单</span></button>
  </div>
</template>
<script setup lang="ts">
import {computed,nextTick,ref,watch,type Component} from 'vue';
import {useRoute} from 'vue-router';
import type {MenuInstance} from 'element-plus';
import {House,Calendar,Bell,ChatDotRound,TrendCharts,Timer,List,Connection,User,Setting} from '@element-plus/icons-vue';
import {sidebarSelection} from '@/utils/sidebarNavigation';
import {configuredSidebar,defaultSidebarPreferences,type SidebarPreferences} from '@/utils/sidebarPreferences';
const props=defineProps<{collapsed:boolean;admin:boolean;devices:boolean;preferences?:SidebarPreferences;canConfigure?:boolean}>();
const emit=defineEmits<{(event:'customize'):void}>();
const route=useRoute(),menu=ref<MenuInstance>();
const icons:Record<string,Component>={home:House,calendar:Calendar,bell:Bell,chat:ChatDotRound,activity:TrendCharts,recovery:Timer,plan:List,device:Connection,user:User,settings:Setting};
const configured=computed(()=>configuredSidebar(props.admin,props.devices,props.preferences || defaultSidebarPreferences()));
const groups=computed(()=>configured.value.groups);
const selection=computed(()=>sidebarSelection(route.path,groups.value));
// Open the current section on navigation, without closing other sections.
watch([()=>route.path,()=>props.collapsed,groups],async()=>{
  if(props.collapsed)return;
  await nextTick();
  if(selection.value.groupId)menu.value?.open(selection.value.groupId);
},{immediate:true});
</script>
<style scoped>
.sidebar-navigation-shell{height:calc(100dvh - 100px);display:flex;flex-direction:column;min-height:0}
.sidebar-navigation{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:#555 transparent;padding-bottom:18px;background:#1a1a1a}
.customize-sidebar{display:flex;align-items:center;gap:14px;flex-shrink:0;width:100%;min-height:48px;padding:0 24px;border:0;border-top:1px solid #343434;background:#1a1a1a;color:#bbb;cursor:pointer;text-align:left;font-size:14px}.customize-sidebar .el-icon{font-size:22px}.customize-sidebar:hover{background:#303030;color:#fff}.customize-sidebar:focus-visible{outline:2px solid #05a9e0;outline-offset:-3px}.customize-sidebar:disabled{opacity:.4;cursor:default}
.sidebar-navigation::-webkit-scrollbar{width:5px}.sidebar-navigation::-webkit-scrollbar-thumb{background:#555;border-radius:0}
.sidebar-menu{border:0;background:transparent;width:100%;--el-menu-bg-color:#1a1a1a;--el-menu-hover-bg-color:#252525;--el-menu-text-color:#c7c7c7;--el-menu-active-color:#fff}
.sidebar-navigation :deep(.el-menu-item),.sidebar-navigation :deep(.el-sub-menu__title){position:relative;margin:0;border-radius:0;height:52px;line-height:52px;padding-left:24px!important;font-size:17px;font-weight:400;letter-spacing:.1px;color:#c7c7c7}
.sidebar-navigation :deep(.el-menu-item .el-icon),.sidebar-navigation :deep(.el-sub-menu__title>.el-icon:not(.el-sub-menu__icon-arrow)){font-size:23px;width:26px;margin-right:14px;color:#05a9e0;flex-shrink:0}
.sidebar-navigation :deep(.sidebar-shortcut>.el-icon){color:#aaa;font-size:21px}
.sidebar-navigation :deep(.el-sub-menu__icon-arrow){font-size:14px;color:#999;right:20px;width:16px;margin:0}
.sidebar-navigation :deep(.el-sub-menu.is-opened>.el-sub-menu__title){background:#242424;color:#eee}
.sidebar-navigation :deep(.el-sub-menu>.el-menu){background:#242424;padding:0 0 8px}
.sidebar-navigation :deep(.el-sub-menu .el-menu-item){padding-left:64px!important;margin:0;height:42px;line-height:42px;font-size:14px;min-width:0;color:#bbb}
.sidebar-navigation :deep(.el-menu-item:hover),.sidebar-navigation :deep(.el-sub-menu__title:hover){background:#2a2a2a;color:#fff}
.sidebar-navigation :deep(.el-menu-item.is-active){background:#303030;color:#fff}
.sidebar-navigation :deep(.el-menu-item.is-active)::before,.sidebar-navigation :deep(.el-sub-menu.is-active:not(.is-opened)>.el-sub-menu__title)::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:#fff}
.sidebar-navigation :deep(.el-sub-menu.is-active>.el-sub-menu__title){color:#fff}
.sidebar-navigation :deep(.el-menu-item.is-active .el-icon){color:#05a9e0}
.sidebar-navigation :deep(.el-menu-item-group__title){display:none}.sidebar-navigation :deep(.sidebar-section){margin-top:14px;padding-top:14px;border-top:1px solid #343434}
.sidebar-external{list-style:none}.sidebar-external a{display:block;padding:0 16px 0 64px;min-height:44px;line-height:44px;text-decoration:none;color:#bbb;font-size:14px}.sidebar-external a:hover{background:#303030;color:white}.sidebar-external a:focus-visible{outline:2px solid #05a9e0;outline-offset:-3px}
.sidebar-navigation :deep(.el-menu--collapse){width:72px}.sidebar-navigation :deep(.el-menu--collapse>.el-menu-item),.sidebar-navigation :deep(.el-menu--collapse .el-sub-menu>.el-sub-menu__title){padding-left:24px!important}.sidebar-navigation :deep(.el-menu--collapse .el-sub-menu__title>span){display:none}
:global(.gaitlogic-sidebar-flyout){--el-menu-bg-color:#242424;--el-menu-text-color:#c7c7c7;--el-menu-hover-bg-color:#303030;--el-menu-active-color:#fff;border-color:#343434!important}
:global(.gaitlogic-sidebar-flyout .el-menu-item.is-active){background:#303030;border-left:4px solid #fff}
:global(.gaitlogic-sidebar-flyout .sidebar-external a){display:block;padding:0 20px;line-height:44px;color:#c7c7c7;text-decoration:none}
</style>
