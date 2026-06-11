<template>
  <div class="page-stack my-page">
    <div>
      <div class="excel-section-title">我的</div>
      <div class="excel-subtitle">常用入口集中在这里，手机端可以从底部导航快速进入。</div>
    </div>

    <section class="shortcut-grid">
      <router-link v-for="item in primaryItems" :key="item.path" :to="myEntryLink(item.path)" class="shortcut-card">
        <el-icon><component :is="item.icon" /></el-icon>
        <div>
          <strong>{{ item.title }}</strong>
          <span>{{ item.desc }}</span>
        </div>
      </router-link>
    </section>

    <section class="panel advanced-panel">
      <el-collapse>
        <el-collapse-item title="高级设置入口" name="advanced">
          <div class="advanced-grid">
            <router-link v-for="item in advancedItems" :key="item.path" :to="myEntryLink(item.path)" class="advanced-link">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </router-link>
          </div>
        </el-collapse-item>
      </el-collapse>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  Calendar,
  DataAnalysis,
  DocumentAdd,
  Grid,
  List,
  Message,
  Setting,
  TrendCharts,
} from "@element-plus/icons-vue";

const primaryItems = [
  { path: "/workouts", title: "我的训练计划", desc: "查看和维护每日训练安排", icon: List },
  { path: "/dashboard", title: "训练统计", desc: "查看跑量、完成率和训练分布", icon: DataAnalysis },
  { path: "/excel-import", title: "Excel 导入", desc: "导入自己的训练计划表", icon: DocumentAdd },
  { path: "/feedback", title: "反馈", desc: "提交问题或使用建议", icon: Message },
];

const advancedItems = [
  { path: "/ai-coach-preference", title: "AI 教练偏好", icon: Setting },
  { path: "/cycles", title: "训练周期", icon: Calendar },
  { path: "/blocks", title: "训练块", icon: Grid },
  { path: "/pace-rules", title: "配速规则", icon: TrendCharts },
];

function myEntryLink(path: string) {
  return { path, query: { from: "/my" } };
}
</script>

<style scoped>
.my-page {
  gap: 14px;
}

.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.shortcut-card,
.advanced-link {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: #172033;
  text-decoration: none;
}

.shortcut-card {
  padding: 16px;
  border: 1px solid #d8dde3;
  border-radius: 6px;
  background: #ffffff;
}

.shortcut-card .el-icon,
.advanced-link .el-icon {
  flex: 0 0 auto;
  color: #1976d2;
  font-size: 22px;
}

.shortcut-card div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.shortcut-card strong {
  font-size: 15px;
}

.shortcut-card span {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.advanced-panel {
  padding: 0 16px;
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding-bottom: 14px;
}

.advanced-link {
  padding: 12px;
  border: 1px solid #e4e7ec;
  border-radius: 6px;
  background: #fbfcfd;
}

@media (max-width: 768px) {
  .shortcut-grid,
  .advanced-grid {
    grid-template-columns: 1fr;
  }

  .shortcut-card {
    padding: 14px;
  }
}
</style>
