<template>
  <section>
    <div class="page-heading">
      <div><div class="eyebrow">SYSTEM PREFERENCES</div><h1>系统设置</h1><p>统一管理跑者端登录入口和公开注册，不影响后台独立登录。</p></div>
      <el-button :disabled="busy" @click="load">重新加载</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <div class="two-columns">
      <article class="card">
        <h2>登录与注册</h2><p>更改影响整个系统。加载成功后才能保存，失败时不会用默认值覆盖已有配置。</p>
        <el-form label-position="top" :disabled="busy || !settings">
          <el-form-item label="跑者端登录方式">
            <el-radio-group v-model="form.auth_entry_mode" class="auth-options">
              <el-radio-button label="standalone">单独登录页</el-radio-button>
              <el-radio-button label="modal">弹窗登录</el-radio-button>
            </el-radio-group>
            <p class="muted">仅调整登录入口，不取消身份验证、用户隔离或管理员权限检查。</p>
          </el-form-item>
          <el-form-item label="公开注册">
            <el-switch v-model="form.allow_public_registration" active-text="允许" inactive-text="关闭" />
            <p class="muted">关闭后不接受公开注册；已有账号仍可登录，管理员用户管理不受影响。</p>
          </el-form-item>
          <p class="muted">最近更新：{{ updatedAt }}</p>
          <el-button type="primary" :loading="busy" :disabled="busy || !settings" @click="save">保存系统设置</el-button>
        </el-form>
      </article>
      <article class="card">
        <h2>配置边界</h2>
        <p>AI 模型参数在 AI 配置中管理；账号角色与状态在用户管理中维护。</p>
        <router-link class="shortcut" to="/ai"><b>AI 配置 →</b><span>模型、额度、冷却与配置草稿。</span></router-link>
        <router-link class="shortcut" to="/users"><b>用户管理 →</b><span>账号状态与管理员角色。</span></router-link>
        <p class="muted">菜单布局、个人训练偏好、Garmin 连接和恢复数据授权仍由用户自己管理，不在此批量修改。</p>
      </article>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { SystemSettings, SystemSettingsPayload } from '@/types/models';
import { errorText } from './api';
import { getConsoleSystemSettings, saveConsoleSystemSettings } from './systemSettings';

const settings = ref<SystemSettings | null>(null), busy = ref(false), error = ref('');
const form = reactive<SystemSettingsPayload>({ auth_entry_mode: 'standalone', allow_public_registration: false });
const updatedAt = computed(() => settings.value?.updated_at?.replace('T', ' ') || '暂无记录');
function apply(value: SystemSettings) {
  settings.value = value;
  form.auth_entry_mode = value.auth_entry_mode;
  form.allow_public_registration = value.allow_public_registration;
}
async function load() {
  if (busy.value) return;
  busy.value = true; error.value = '';
  try { apply(await getConsoleSystemSettings()); }
  catch (cause) { settings.value = null; error.value = errorText(cause); }
  finally { busy.value = false; }
}
async function save() {
  if (busy.value || !settings.value) return;
  // Lock the form through confirmation so the submitted snapshot is explicit.
  busy.value = true; error.value = '';
  const payload = { ...form };
  try {
    await ElMessageBox.confirm('确认保存？修改将影响所有用户的跑者端登录入口和公开注册。后台仍保持独立管理员登录。', '保存系统设置', {
      type: 'warning', confirmButtonText: '确认保存', cancelButtonText: '取消',
    });
  } catch { busy.value = false; return; }
  try { apply(await saveConsoleSystemSettings(payload)); ElMessage.success('系统设置已保存'); }
  catch (cause) { error.value = errorText(cause); }
  finally { busy.value = false; }
}
onMounted(load);
</script>
<style scoped>
.auth-options{display:flex;flex-wrap:wrap;max-width:100%}.muted{width:100%}
@media(max-width:600px){.auth-options :deep(.el-radio-button__inner){min-height:44px;display:flex;align-items:center}}
</style>
