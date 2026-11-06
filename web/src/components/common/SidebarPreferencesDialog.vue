<template>
  <el-dialog :model-value="modelValue" title="自定义菜单" width="600px" :z-index="3100" class="sidebar-preferences-dialog" append-to-body @update:model-value="emit('update:modelValue', $event)">
    <p class="preference-hint">电脑侧栏与手机“更多”共用分组设置，手机底部入口可单独选择。设置保存在当前浏览器、当前账号，不跨设备同步。</p>
    <h3>常用入口</h3>
    <p class="preference-hint">最多选择 6 个，已选功能移到顶部，不在分组中重复显示。</p>
    <el-select v-model="draft.shortcuts" multiple :multiple-limit="6" popper-class="sidebar-preference-options" placeholder="选择常用功能" aria-label="选择常用入口" style="width:100%">
      <el-option v-for="item in choices" :key="item.path" :value="item.path" :label="item.label" />
    </el-select>
    <div v-for="(path, index) in draft.shortcuts" :key="path" class="preference-row">
      <span>{{ choices.find(item => item.path === path)?.label }}</span>
      <div class="order-actions"><button :disabled="index===0" :aria-label="`上移常用入口${label(path)}`" @click="move(draft.shortcuts, index, -1)">↑</button><button :disabled="index===draft.shortcuts.length-1" :aria-label="`下移常用入口${label(path)}`" @click="move(draft.shortcuts, index, 1)">↓</button></div>
    </div>
    <h3>手机底部入口</h3>
    <p class="preference-hint">最多 4 个，按下方顺序显示；“更多”始终保留，方便访问其余功能和恢复设置。</p>
    <el-select v-model="draft.mobileShortcuts" multiple :multiple-limit="4" popper-class="sidebar-preference-options" placeholder="选择手机常用功能" aria-label="选择手机底部入口" style="width:100%">
      <el-option v-for="item in choices" :key="item.path" :value="item.path" :label="item.label" />
    </el-select>
    <div v-for="(path,index) in draft.mobileShortcuts" :key="path" class="preference-row">
      <span>{{ label(path) }}</span>
      <div class="order-actions"><button :disabled="index===0" :aria-label="`上移手机入口${label(path)}`" @click="move(draft.mobileShortcuts,index,-1)">↑</button><button :disabled="index===draft.mobileShortcuts.length-1" :aria-label="`下移手机入口${label(path)}`" @click="move(draft.mobileShortcuts,index,1)">↓</button></div>
    </div>
    <h3>功能分组</h3>
    <p class="preference-hint">取消勾选仅隐藏导航，不会删除数据或更改权限。新功能默认显示。</p>
    <el-collapse>
      <div v-for="(group, index) in editingGroups" :key="group.id" class="preference-group">
        <div class="preference-row">
          <el-checkbox :model-value="!draft.hiddenGroups.includes(group.id)" @update:model-value="toggle(draft.hiddenGroups, group.id, Boolean($event))">{{ group.label }}</el-checkbox>
          <div class="order-actions"><button :disabled="index===0" :aria-label="`上移${group.label}`" @click="moveGroup(index,-1)">↑</button><button :disabled="index===editingGroups.length-1" :aria-label="`下移${group.label}`" @click="moveGroup(index,1)">↓</button></div>
        </div>
        <el-collapse-item :title="`配置${group.label}的功能`" :name="group.id">
          <div v-for="(item, childIndex) in group.items" :key="item.path" class="preference-row child-row">
            <el-checkbox :model-value="!draft.hiddenItems.includes(item.path)" @update:model-value="toggle(draft.hiddenItems,item.path,Boolean($event))">{{ item.label }}</el-checkbox>
            <div class="order-actions"><button :disabled="childIndex===0" :aria-label="`上移${item.label}`" @click="moveItem(group.id,childIndex,-1)">↑</button><button :disabled="childIndex===group.items.length-1" :aria-label="`下移${item.label}`" @click="moveItem(group.id,childIndex,1)">↓</button></div>
          </div>
        </el-collapse-item>
      </div>
    </el-collapse>
    <template #footer><div class="preference-footer"><el-button @click="draft=defaultSidebarPreferences()">恢复默认</el-button><div><el-button @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" @click="emit('save',normalizeSidebarPreferences(draft))">保存设置</el-button></div></div></template>
  </el-dialog>
</template>
<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import {sidebarGroups,sidebarShortcuts} from '@/utils/sidebarNavigation';
import {defaultSidebarPreferences,normalizeSidebarPreferences,ordered,type SidebarPreferences} from '@/utils/sidebarPreferences';
const props=defineProps<{modelValue:boolean;preferences:SidebarPreferences;admin:boolean;devices:boolean}>();
const emit=defineEmits<{(event:'update:modelValue',value:boolean):void;(event:'save',value:SidebarPreferences):void}>();
const draft=ref(defaultSidebarPreferences());
const available=computed(()=>sidebarGroups(props.admin,props.devices));
const choices=computed(()=>[...sidebarShortcuts,...available.value.flatMap(group=>group.items).filter(item=>!item.external)]);
const editingGroups=computed(()=>ordered(available.value,draft.value.groupOrder,group=>group.id).map(group=>({...group,items:ordered(group.items,draft.value.itemOrder[group.id] || [],item=>item.path)})));
watch(()=>props.modelValue,open=>{if(open){draft.value=normalizeSidebarPreferences(props.preferences);draft.value.shortcuts=draft.value.shortcuts.filter(path=>choices.value.some(item=>item.path===path));draft.value.mobileShortcuts=draft.value.mobileShortcuts.filter(path=>choices.value.some(item=>item.path===path));}});
function label(path:string){return choices.value.find(item=>item.path===path)?.label || '';}
function toggle(hidden:string[],id:string,visible:boolean){const index=hidden.indexOf(id);if(visible && index>=0)hidden.splice(index,1);else if(!visible && index<0)hidden.push(id);}
function move(items:string[],index:number,delta:number){const next=index+delta;if(next<0 || next>=items.length)return;[items[index],items[next]]=[items[next],items[index]];}
function moveGroup(index:number,delta:number){const ids=editingGroups.value.map(group=>group.id);move(ids,index,delta);draft.value.groupOrder=ids;}
function moveItem(id:string,index:number,delta:number){const paths=editingGroups.value.find(group=>group.id===id)!.items.map(item=>item.path);move(paths,index,delta);draft.value.itemOrder[id]=paths;}
</script>
<style scoped>
.preference-hint{font-size:13px;line-height:1.6;color:#667085}.preference-row{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:44px}.preference-group{border-bottom:1px solid #e5e7eb;padding:8px 0}.child-row{padding-left:12px}.order-actions{display:flex;gap:6px;flex-shrink:0}.order-actions button{width:36px;height:36px;border:1px solid #d5dce5;border-radius:6px;background:#fff;cursor:pointer;color:#344054}.order-actions button:disabled{opacity:.3;cursor:default}.order-actions button:focus-visible{outline:2px solid #1686ce}.preference-footer{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}
:global(.sidebar-preferences-dialog){display:flex;flex-direction:column;max-width:calc(100vw - 24px);max-height:calc(100dvh - 32px);margin-top:6vh!important}:global(.sidebar-preferences-dialog .el-dialog__body){max-height:65dvh;min-height:0;overflow-y:auto;flex:1}:global(.sidebar-preferences-dialog .el-dialog__footer){flex-shrink:0}:global(.sidebar-preference-options){z-index:3200!important}
.preference-footer{width:100%}.preference-footer>div{display:flex;gap:8px}.preference-footer>div :deep(.el-button){margin-left:0}
@media(max-width:480px){.preference-footer{display:grid;grid-template-columns:1fr}.preference-footer>div{display:grid;grid-template-columns:1fr 1fr}.order-actions button{width:44px;height:44px}.preference-row :deep(.el-checkbox){height:auto;min-height:44px;white-space:normal}.preference-row :deep(.el-checkbox__label){white-space:normal}}
</style>
