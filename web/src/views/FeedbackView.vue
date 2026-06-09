<template>
  <div class="page-stack feedback-page">
    <section class="feedback-hero">
      <div>
        <div class="hero-kicker">内测反馈</div>
        <h2>反馈</h2>
        <p>遇到看不懂、用不顺、数据不对的地方，都可以直接记下来。</p>
      </div>
    </section>

    <section class="feedback-grid">
      <article class="panel feedback-form-card">
        <div class="panel-head">
          <div>
            <h3>提交反馈</h3>
            <p>反馈会绑定当前登录用户，便于后续跟进。</p>
          </div>
        </div>
        <el-form label-position="top">
          <el-form-item label="反馈类型">
            <el-select v-model="form.feedback_type" style="width: 100%">
              <el-option
                v-for="item in feedbackTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="页面地址">
            <el-input v-model="form.page_url" placeholder="/dashboard" />
          </el-form-item>
          <el-form-item label="反馈内容">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="6"
              maxlength="1000"
              show-word-limit
              placeholder="例如：这里的完成率我看不懂"
            />
          </el-form-item>
          <el-form-item label="联系方式（可选）">
            <el-input v-model="form.contact" placeholder="微信、邮箱或其他联系方式" />
          </el-form-item>
          <div class="form-actions">
            <el-button type="primary" :loading="submitting" @click="submit">提交反馈</el-button>
          </div>
        </el-form>
      </article>

      <article class="panel feedback-tip-card">
        <h3>可以反馈什么？</h3>
        <ul>
          <li>页面报错、接口失败、数据不显示</li>
          <li>训练逻辑、统计口径或配速区间看不懂</li>
          <li>Excel 导入流程不顺</li>
          <li>希望增加的跑者工作流</li>
        </ul>
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>我的反馈</h3>
          <p>这里只显示你自己提交过的反馈。</p>
        </div>
        <el-button :icon="Refresh" @click="loadFeedback">刷新</el-button>
      </div>
      <el-table :data="items" v-loading="loading">
        <el-table-column label="类型" width="130">
          <template #default="{ row }">{{ feedbackTypeLabel(row.feedback_type) }}</template>
        </el-table-column>
        <el-table-column prop="page_url" label="页面" width="180" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" min-width="320" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useRoute } from "vue-router";

import { listMyFeedback, submitFeedback } from "@/api/feedback";
import type { FeedbackItem, FeedbackPayload, FeedbackType } from "@/types/models";

const route = useRoute();

const feedbackTypeOptions: Array<{ label: string; value: FeedbackType }> = [
  { label: "Bug", value: "bug" },
  { label: "功能建议", value: "suggestion" },
  { label: "看不懂 / 不清楚", value: "confusing" },
  { label: "训练逻辑", value: "training_logic" },
  { label: "其他", value: "other" },
];

const form = reactive<FeedbackPayload>({
  feedback_type: "bug",
  page_url: String(route.query.page || route.query.from || route.fullPath || "/feedback"),
  content: "",
  contact: "",
});

const items = ref<FeedbackItem[]>([]);
const loading = ref(false);
const submitting = ref(false);

function feedbackTypeLabel(value: FeedbackType) {
  return feedbackTypeOptions.find((item) => item.value === value)?.label || value;
}

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

async function loadFeedback() {
  loading.value = true;
  try {
    items.value = await listMyFeedback();
  } finally {
    loading.value = false;
  }
}

async function submit() {
  if (!form.content.trim()) {
    ElMessage.warning("请填写反馈内容");
    return;
  }
  submitting.value = true;
  try {
    const result = await submitFeedback({
      feedback_type: form.feedback_type,
      page_url: form.page_url,
      content: form.content.trim(),
      contact: form.contact || null,
    });
    ElMessage.success(result.message || "反馈提交成功");
    form.content = "";
    await loadFeedback();
  } finally {
    submitting.value = false;
  }
}

onMounted(loadFeedback);
</script>

<style scoped>
.feedback-page .panel {
  padding: 22px;
}

.feedback-hero {
  padding: 22px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--shadow-sm);
}

.hero-kicker {
  margin-bottom: 8px;
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.feedback-hero h2 {
  margin: 0;
  color: #172033;
  font-size: 26px;
}

.feedback-hero p {
  margin: 8px 0 0;
  color: #667085;
}

.feedback-grid {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) 320px;
  gap: 16px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-head h3,
.feedback-tip-card h3 {
  margin: 0;
  color: #1f2937;
  font-size: 17px;
  font-weight: 650;
}

.panel-head p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.feedback-tip-card {
  align-self: start;
}

.feedback-tip-card ul {
  display: grid;
  gap: 10px;
  margin: 16px 0 0;
  padding-left: 20px;
  color: #344054;
  line-height: 1.7;
}

@media (max-width: 980px) {
  .feedback-grid {
    grid-template-columns: 1fr;
  }
}
</style>
