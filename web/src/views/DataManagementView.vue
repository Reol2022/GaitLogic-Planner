<template>
  <div class="page-stack data-management-page">
    <PageHeader title="数据管理" subtitle="导入、补录、导出和历史记录集中在这里。" />

    <section class="management-grid">
      <button v-for="item in items" :key="item.path" type="button" class="management-card" @click="router.push(item.path)">
        <el-icon><component :is="item.icon" /></el-icon>
        <strong>{{ item.title }}</strong>
        <span>{{ item.desc }}</span>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { DocumentAdd, Download, FolderOpened, Upload } from "@element-plus/icons-vue";

const router = useRouter();
const items = [
  { path: "/workout-import", title: "训练记录导入", desc: "批量补录已经完成的训练。", icon: Upload },
  { path: "/plan-imports", title: "课表导入", desc: "从 Excel、CSV 或文本生成计划草稿。", icon: DocumentAdd },
  { path: "/data-sync", title: "数据同步", desc: "管理运动平台连接和异常活动。", icon: FolderOpened },
  { path: "/workouts", title: "计划数据查看", desc: "查看当前周期下的每日训练。", icon: Download },
];
</script>

<style scoped>
.data-management-page {
  gap: 14px;
}

.management-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.management-card {
  display: grid;
  justify-items: start;
  gap: 8px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  color: #172033;
  text-align: left;
  box-shadow: var(--card-shadow);
  cursor: pointer;
}

.management-card .el-icon {
  color: #1976d2;
  font-size: 24px;
}

.management-card span {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .data-management-page {
    padding: 14px;
  }

  .management-grid {
    grid-template-columns: 1fr;
  }
}
</style>
