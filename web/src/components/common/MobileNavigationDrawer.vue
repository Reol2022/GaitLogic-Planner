<template>
  <el-drawer :model-value="modelValue" title="更多功能" direction="rtl" size="min(360px, 92vw)" :z-index="3000" append-to-body @update:model-value="emit('update:modelValue',$event)">
    <nav aria-label="手机完整菜单" class="mobile-menu-list">
      <router-link class="mobile-menu-profile" to="/my" @click="close">我的主页 <span>账户与设置 →</span></router-link>
      <div v-if="configured.shortcuts.length" class="mobile-menu-shortcuts"><router-link v-for="item in configured.shortcuts" :key="item.path" :to="item.path" :aria-current="selected===item.path?'page':undefined" @click="close">{{ item.label }}</router-link></div>
      <el-collapse v-model="expanded">
        <el-collapse-item v-for="group in configured.groups" :key="group.id" :name="group.id" :title="group.label">
          <template v-for="item in group.items" :key="item.path">
            <a v-if="item.external" :href="item.path" @click="close">{{ item.label }}</a>
            <router-link v-else :to="item.path" :aria-current="selected===item.path?'page':undefined" @click="close">{{ item.label }}</router-link>
          </template>
        </el-collapse-item>
      </el-collapse>
      <p v-if="!configured.shortcuts.length && !configured.groups.length" class="mobile-menu-empty">菜单已隐藏，可在下方恢复默认或重新选择。</p>
    </nav>
    <template #footer><el-button style="width:100%;min-height:44px" @click="close();emit('customize')">自定义菜单</el-button></template>
  </el-drawer>
</template>
<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import {useRoute} from 'vue-router';
import {configuredSidebar,type SidebarPreferences} from '@/utils/sidebarPreferences';
import {sidebarSelection} from '@/utils/sidebarNavigation';
const props=defineProps<{modelValue:boolean;preferences:SidebarPreferences;admin:boolean;devices:boolean}>();
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'customize'):void}>();
const route=useRoute();const expanded=ref<string[]>([]);
const configured=computed(()=>{
  const result=configuredSidebar(props.admin,props.devices,props.preferences);
  return {shortcuts:result.shortcuts.filter(item=>item.path!=='/my'),groups:result.groups.map(group=>({...group,items:group.items.filter(item=>item.path!=='/my')})).filter(group=>group.items.length)};
});
const selected=computed(()=>sidebarSelection(route.path,configured.value.groups).activePath);
function close(){emit('update:modelValue',false);}
watch(()=>props.modelValue,open=>{if(open){const group=sidebarSelection(route.path,configured.value.groups).groupId;if(group && !expanded.value.includes(group))expanded.value.push(group);}});
watch(()=>route.fullPath,close);
</script>
<style scoped>
.mobile-menu-list a{display:flex;align-items:center;min-height:46px;padding:10px 12px;color:#344054;text-decoration:none;border-radius:8px;overflow-wrap:anywhere}.mobile-menu-list a:hover,.mobile-menu-list a[aria-current=page]{background:#eaf4ff;color:#0874c8}.mobile-menu-profile{display:flex;justify-content:space-between;font-weight:600;border-bottom:1px solid #e5e7eb}.mobile-menu-profile span{font-size:12px;font-weight:400;color:#667085}.mobile-menu-shortcuts{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:12px 0}.mobile-menu-shortcuts a{background:#f4f6f8}.mobile-menu-empty{color:#667085;font-size:14px;line-height:1.7}.mobile-menu-list :deep(.el-collapse-item__header){font-size:15px;min-height:48px}.mobile-menu-list a:focus-visible{outline:2px solid #1686ce;outline-offset:-2px}
</style>
