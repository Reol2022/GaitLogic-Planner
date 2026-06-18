<template>
  <div class="page-stack admin-system-page">
    <PageHeader title="系统设置" subtitle="配置登录入口、注册开关和系统管理入口。" />

    <section class="settings-grid">
      <article class="panel auth-mode-panel">
        <div class="panel-head">
          <h3>登录入口</h3>
          <p>可在传统单独登录页和主系统弹窗登录之间切换。弹窗模式下，用户访问需要权限的数据时再弹出登录框。</p>
        </div>
        <el-form label-position="top">
          <el-form-item label="登录方式">
            <el-radio-group v-model="form.auth_entry_mode">
              <el-radio-button label="standalone">单独登录页</el-radio-button>
              <el-radio-button label="modal">弹窗登录</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="公开注册">
            <el-switch
              v-model="form.allow_public_registration"
              active-text="允许"
              inactive-text="关闭"
            />
          </el-form-item>
          <el-button type="primary" :loading="saving" @click="saveSettings">保存系统设置</el-button>
        </el-form>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>账号与权限</h3>
          <p>当前系统使用账号角色控制后台权限，管理员可维护用户角色和状态。</p>
        </div>
        <el-button type="primary" @click="router.push('/admin/users')">进入用户管理</el-button>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>AI 生成</h3>
          <p>模型、Base URL、API Key、额度、冷却时间和生成参数统一在模型设置中配置。</p>
        </div>
        <el-button type="primary" @click="router.push('/admin/ai-settings')">进入 AI 模型设置</el-button>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>训练数据范围</h3>
          <p>当前项目仍聚焦训练计划、训练日志、配速规则、复盘统计和 AI 课表草稿。</p>
        </div>
        <el-tag effect="light">Garmin / App / 商业化未启用</el-tag>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>安全提示</h3>
          <p>停用用户后，该用户无法继续登录；已登录令牌会在下一次鉴权时被状态检查拦截。</p>
        </div>
        <el-tag type="warning" effect="light">管理员请至少保留一个 active admin</el-tag>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { getAdminSystemSettings, updateAdminSystemSettings } from "@/api/admin";
import type { SystemSettingsPayload } from "@/types/models";
import { cacheSystemSettings } from "@/utils/systemSettingsCache";

const router = useRouter();
const saving = ref(false);
const form = reactive<SystemSettingsPayload>({
  auth_entry_mode: "standalone",
  allow_public_registration: true,
});

async function loadSettings() {
  const settings = await getAdminSystemSettings();
  form.auth_entry_mode = settings.auth_entry_mode;
  form.allow_public_registration = settings.allow_public_registration;
  cacheSystemSettings(settings);
}

async function saveSettings() {
  saving.value = true;
  try {
    const result = await updateAdminSystemSettings(form);
    form.auth_entry_mode = result.auth_entry_mode;
    form.allow_public_registration = result.allow_public_registration;
    cacheSystemSettings(result);
    ElMessage.success("系统设置已保存");
  } finally {
    saving.value = false;
  }
}

onMounted(loadSettings);
</script>

<style scoped>
.admin-hero {
  padding: 22px;
}

.admin-hero span {
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.admin-hero h2 {
  margin: 6px 0 0;
  color: #172033;
}

.admin-hero p,
.panel-head p {
  margin: 6px 0 0;
  color: #667085;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  display: grid;
  align-content: space-between;
  gap: 18px;
  padding: 22px;
}

.auth-mode-panel {
  align-content: start;
}

.panel-head h3 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
