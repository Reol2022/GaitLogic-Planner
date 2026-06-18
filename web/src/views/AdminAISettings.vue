<template>
  <div class="page-stack admin-ai-page">
    <PageHeader title="AI 模型设置" subtitle="配置全站 AI 课表生成使用的 OpenAI-compatible 模型。">
      <template #actions>
        <el-tag :type="form.has_api_key ? 'success' : 'warning'" effect="light">
          {{ form.has_api_key ? `API Key 已配置：${form.api_key_preview}` : "API Key 未配置" }}
        </el-tag>
      </template>
    </PageHeader>

    <section class="settings-grid">
      <article class="panel">
        <div class="panel-head">
          <h3>模型接入</h3>
          <p>选择预设会自动填入常用 Base URL 和模型名，仍然可以手动修改。</p>
        </div>
        <el-form label-position="top">
          <el-form-item label="模型提供商">
            <el-select v-model="form.provider" style="width: 100%" @change="applyProviderPreset">
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="OpenAI-compatible" value="openai" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="form.base_url" placeholder="https://api.deepseek.com" />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-select v-model="form.model_name" allow-create filterable style="width: 100%">
              <el-option label="deepseek-v4-flash" value="deepseek-v4-flash" />
              <el-option label="deepseek-v4-pro" value="deepseek-v4-pro" />
              <el-option label="deepseek-chat" value="deepseek-chat" />
              <el-option label="deepseek-reasoner" value="deepseek-reasoner" />
              <el-option label="gpt-4.1-mini" value="gpt-4.1-mini" />
              <el-option label="gpt-4.1" value="gpt-4.1" />
            </el-select>
          </el-form-item>
          <el-form-item label="API Key">
            <el-input
              v-model="apiKeyInput"
              type="password"
              show-password
              placeholder="留空表示不修改；输入新 Key 会覆盖"
            />
          </el-form-item>
          <el-form-item label="超时时间（秒）">
            <el-input-number v-model="form.timeout_seconds" :min="10" :max="600" style="width: 100%" />
          </el-form-item>
        </el-form>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>使用限制</h3>
          <p>用于控制每个用户的 AI 课表生成频率。</p>
        </div>
        <el-form label-position="top">
          <el-form-item label="每人每日可生成次数">
            <el-input-number v-model="form.ai_plan_daily_limit" :min="0" :max="1000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="两次生成冷却时间（秒）">
            <el-input-number v-model="form.ai_plan_cooldown_seconds" :min="0" :max="86400" style="width: 100%" />
          </el-form-item>
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="将每日次数设为 0 可以临时关闭 AI 课表生成。"
          />
        </el-form>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>生成参数</h3>
          <p>训练计划需要稳定输出，建议不要把 temperature 调得太高。</p>
        </div>
        <el-form label-position="top">
          <el-form-item label="temperature">
            <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.05" show-input />
          </el-form-item>
          <el-form-item label="top_p">
            <el-slider v-model="form.top_p" :min="0.05" :max="1" :step="0.05" show-input />
          </el-form-item>
        </el-form>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>输出长度</h3>
          <p>计划周数越多，模型需要的输出 token 越多。</p>
        </div>
        <el-form label-position="top">
          <el-form-item label="每周 max_tokens">
            <el-input-number v-model="form.max_tokens_per_week" :min="500" :max="10000" :step="100" style="width: 100%" />
          </el-form-item>
          <el-form-item label="max_tokens 上限">
            <el-input-number v-model="form.max_tokens_cap" :min="4096" :max="128000" :step="1000" style="width: 100%" />
          </el-form-item>
        </el-form>
      </article>
    </section>

    <section class="panel footer-panel">
      <div>
        <h3>当前状态</h3>
        <p>最后更新：{{ form.updated_at ? form.updated_at.replace("T", " ").slice(0, 16) : "暂无" }}</p>
      </div>
      <div class="footer-actions">
        <el-button @click="loadSettings">重新加载</el-button>
        <el-button type="primary" :loading="saving" @click="saveSettings">保存设置</el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { getAdminAISettings, updateAdminAISettings } from "@/api/admin";
import type { AdminAISettings, AdminAISettingsPayload } from "@/types/models";

const apiKeyInput = ref("");
const saving = ref(false);

const form = reactive<AdminAISettings>({
  provider: "deepseek",
  base_url: "https://api.deepseek.com",
  model_name: "deepseek-v4-flash",
  timeout_seconds: 120,
  ai_plan_daily_limit: 3,
  ai_plan_cooldown_seconds: 60,
  temperature: 0.4,
  top_p: 0.9,
  max_tokens_per_week: 1600,
  max_tokens_cap: 24000,
  has_api_key: false,
  api_key_preview: null,
  updated_at: null,
});

const providerPresets: Record<string, { base_url: string; model_name: string }> = {
  deepseek: { base_url: "https://api.deepseek.com", model_name: "deepseek-v4-flash" },
  openai: { base_url: "https://api.openai.com/v1", model_name: "gpt-4.1-mini" },
  custom: { base_url: form.base_url, model_name: form.model_name },
};

function assignForm(payload: AdminAISettings) {
  Object.assign(form, payload);
  apiKeyInput.value = "";
}

async function loadSettings() {
  const result = await getAdminAISettings();
  assignForm(result);
}

function applyProviderPreset() {
  const preset = providerPresets[form.provider];
  if (!preset || form.provider === "custom") return;
  form.base_url = preset.base_url;
  form.model_name = preset.model_name;
}

async function saveSettings() {
  saving.value = true;
  try {
    const payload: AdminAISettingsPayload = {
      provider: form.provider,
      base_url: form.base_url,
      model_name: form.model_name,
      api_key: apiKeyInput.value || null,
      timeout_seconds: form.timeout_seconds,
      ai_plan_daily_limit: form.ai_plan_daily_limit,
      ai_plan_cooldown_seconds: form.ai_plan_cooldown_seconds,
      temperature: form.temperature,
      top_p: form.top_p,
      max_tokens_per_week: form.max_tokens_per_week,
      max_tokens_cap: form.max_tokens_cap,
    };
    const result = await updateAdminAISettings(payload);
    assignForm(result);
    ElMessage.success("AI 设置已保存");
  } finally {
    saving.value = false;
  }
}

onMounted(loadSettings);
</script>

<style scoped>
.admin-hero,
.footer-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px;
}

.admin-hero span {
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.admin-hero h2,
.footer-panel h3 {
  margin: 6px 0 0;
  color: #172033;
}

.admin-hero p,
.footer-panel p,
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
  padding: 22px;
}

.panel-head {
  margin-bottom: 16px;
}

.panel-head h3 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

.footer-actions {
  display: flex;
  gap: 10px;
}

@media (max-width: 1080px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .admin-hero,
  .footer-panel {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
