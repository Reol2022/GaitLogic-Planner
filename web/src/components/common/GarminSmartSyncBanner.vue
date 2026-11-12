<template>
  <div v-if="active" class="smart-sync-banner" role="status">正在更新 Garmin 数据，当前页面仍显示已有记录。</div>
</template>
<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { checkSmartSync, getSmartSync, type SyncFreshness } from '@/api/smartSync';
const state = ref<SyncFreshness | null>(null);
const active = computed(() => ['QUEUED', 'RUNNING'].includes(state.value?.status ?? ''));
let timer: ReturnType<typeof setTimeout> | undefined;
let stopped = false;
let attempts = 0;
async function poll(first = false) {
  try {
    const value = await (first ? checkSmartSync() : getSmartSync());
    if (stopped) return;
    const wasActive = active.value;
    state.value = value;
    if (wasActive && !active.value) window.dispatchEvent(new CustomEvent('garmin-facts-updated'));
    if (active.value && ++attempts <= 60) timer = setTimeout(() => void poll(), Math.min(15000, 3000 + attempts * 500));
  } catch { /* Optional device freshness never blocks the page or login. */ }
}
onMounted(() => void poll(true));
onBeforeUnmount(() => { stopped = true; if (timer) clearTimeout(timer); });
</script>
<style scoped>
.smart-sync-banner{padding:8px 18px;background:var(--surface);color:var(--muted);font-size:13px;border-bottom:1px solid var(--line-soft)}
</style>
