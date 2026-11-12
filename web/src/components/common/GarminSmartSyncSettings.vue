<template>
  <section v-if="state && state.status !== 'DISABLED'" class="smart-settings" aria-label="Garmin 自动同步设置">
    <strong>自动更新 Garmin 数据</strong>
    <label><input v-model="form.enabled" type="checkbox" />开启自动同步（登录、定时与 MCP 查询）</label>
    <label>检查频率 <select v-model.number="form.interval_minutes"><option :value="30">30 分钟</option><option :value="60">1 小时</option><option :value="180">3 小时</option><option :value="1440">每天</option></select></label>
    <label><input v-model="form.recovery_enabled" type="checkbox" />同时自动同步睡眠、HRV 等恢复数据</label>
    <small>恢复数据需单独同意；MCP 读取仍需额外授权。关闭不影响手动同步。</small>
    <p>活动最近成功：{{ state.last_success_by_scope.activities || '暂无' }} · 恢复最近成功：{{ state.last_success_by_scope.recovery || '暂无' }}</p>
    <p role="status">{{ statusText }}<span v-if="state.next_retry_at"> · 下次允许重试：{{ state.next_retry_at }}</span></p>
    <p v-if="error" role="alert">{{ error }}</p>
    <el-button :loading="saving" @click="save">保存自动同步设置</el-button>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { getSmartSync, saveSmartSync, type SyncFreshness } from '@/api/smartSync';
const state = ref<SyncFreshness | null>(null);
const form = reactive({ enabled: false, interval_minutes: 30, recovery_enabled: false });
const saving = ref(false), error = ref('');
const statusText = computed(() => state.value?.status === 'REAUTH_REQUIRED' ? '连接已失效，请重新连接 Garmin' :
  state.value?.error_category ? `最近同步未完成：${state.value.error_category}` :
  ({ QUEUED: '等待后台同步', RUNNING: '正在同步', FRESH: '数据近期已更新', STALE: '等待下一次更新', AUTO_SYNC_DISABLED: '自动同步已关闭' } as Record<string,string>)[state.value?.status ?? ''] || '暂不可用');
async function save() {
  saving.value = true; error.value = '';
  try { state.value = await saveSmartSync({ ...form }); }
  catch { error.value = '设置保存失败，请稍后重试。'; }
  finally { saving.value = false; }
}
onMounted(async () => {
  try { state.value = await getSmartSync(); Object.assign(form, { enabled: state.value.enabled, interval_minutes: state.value.interval_minutes, recovery_enabled: state.value.recovery_enabled }); }
  catch { /* Existing manual sync remains usable when Smart Sync is unavailable. */ }
});
</script>
<style scoped>
.smart-settings{display:grid;gap:12px;padding:16px 0;border-bottom:1px solid var(--line-soft);margin-bottom:16px}.smart-settings label{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.smart-settings p,.smart-settings small{margin:0;color:var(--muted);overflow-wrap:anywhere;font-size:13px}.smart-settings select{padding:8px;max-width:100%}.smart-settings input{min-width:18px;min-height:18px}
</style>
