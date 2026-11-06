<template>
  <span class="gilo-avatar" :class="{ 'is-active': active, 'is-hero': hero }" aria-hidden="true">
    <span class="gilo-orbit" /><span class="gilo-core"><svg viewBox="0 0 48 48" fill="none"><path d="M32 15a13 13 0 1 0 3 17V24H24" stroke="currentColor" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/><path d="m28 11 7 3-5 5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
    <span v-if="hero" class="gilo-satellite satellite-one" /><span v-if="hero" class="gilo-satellite satellite-two" />
  </span>
</template>
<script setup lang="ts">
defineProps<{active?:boolean;hero?:boolean}>();
</script>
<style scoped>
.gilo-avatar{position:relative;display:inline-grid;width:32px;height:32px;flex-shrink:0;place-items:center;isolation:isolate}.gilo-core{position:relative;display:grid;width:88%;height:88%;place-items:center;border:1px solid #ffffff70;border-radius:34%;color:#fff;background:radial-gradient(circle at 22% 18%,#64e5e6 0,transparent 50%),linear-gradient(135deg,#1c85a6,#5063c9 65%,#8b67b4);box-shadow:0 4px 12px #4e83b62b;overflow:hidden}.gilo-core svg{width:76%;height:76%}.gilo-orbit{position:absolute;inset:0;border:1px solid #93ccd45c;border-radius:36%;transform:rotate(15deg)}.is-active .gilo-orbit{animation:gilo-orbit 5s linear infinite}.is-active .gilo-core{animation:gilo-breathe 2.8s ease-in-out infinite}.is-hero{width:100px;height:100px;margin:12px auto 20px}.is-hero .gilo-core{border-radius:34%;box-shadow:0 12px 38px #6372ba38,inset 0 0 15px #ffffff24}.is-hero .gilo-orbit{inset:-8px;border-radius:38%;border-color:#83cfd180}.gilo-satellite{position:absolute;width:7px;height:7px;border-radius:50%;background:#76d8d2;box-shadow:0 0 12px #75ddd1aa}.satellite-one{top:0;right:-11px}.satellite-two{bottom:6px;left:-13px;width:4px;height:4px;background:#a39bdb}.is-active .gilo-satellite{animation:gilo-breathe 3s ease-in-out infinite}@keyframes gilo-orbit{to{transform:rotate(375deg)}}@keyframes gilo-breathe{50%{opacity:.7;transform:translateY(-3px)}}@media(prefers-reduced-motion:reduce){.gilo-avatar *{animation:none!important;transition:none!important}}@media(max-width:768px){.is-hero{width:70px;height:70px;margin:8px auto 15px}}
</style>
