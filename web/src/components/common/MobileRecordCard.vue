<template>
  <article class="mobile-record-card">
    <header><strong>{{ title }}</strong><slot name="status" /></header>
    <div class="mobile-record-content"><slot /></div>
    <footer v-if="$slots.actions"><slot name="actions" /></footer>
  </article>
</template>
<script setup lang="ts">defineProps<{title:string}>();</script>
<style>
.mobile-record-list{display:none}
@media(max-width:768px){.mobile-record-list{display:grid;gap:12px;min-width:0}.desktop-record-table{display:none!important}}
</style>
<style scoped>
.mobile-record-card{min-width:0;padding:16px;border:1px solid #dfe6ed;border-radius:12px;background:#fff;overflow-wrap:anywhere}.mobile-record-card header{display:flex;gap:10px;justify-content:space-between;align-items:flex-start}.mobile-record-card header strong{min-width:0;font-size:14px;line-height:1.6}.mobile-record-content{font-size:13px;line-height:1.7;color:#526579}.mobile-record-content :deep(p){margin:8px 0;overflow-wrap:anywhere}.mobile-record-card footer{display:flex;flex-wrap:wrap;gap:8px;border-top:1px solid #edf0f4;margin-top:12px;padding-top:12px}.mobile-record-card footer :deep(.el-button){min-height:44px;margin:0;flex:1 1 100px;white-space:normal;height:auto}.mobile-record-card :deep(dl){display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}.mobile-record-card :deep(dt){font-size:11px;color:#6d7d8d}.mobile-record-card :deep(dd){margin:2px 0 0;font-size:14px;color:#23384c}
</style>
