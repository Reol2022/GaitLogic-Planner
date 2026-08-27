<template>
  <div class="page-stack my-page">
    <PageHeader title="我的" subtitle="常用入口集中在这里，手机端可以从底部导航快速进入。" />

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
import { computed, onMounted, ref } from "vue";
import {
  Calendar,
  ChatDotRound,
  Connection,
  DataAnalysis,
  DocumentAdd,
  Bell,
  FolderOpened,
  Grid,
  List,
  Message,
  Memo,
  Setting,
  TrendCharts,
} from "@element-plus/icons-vue";
import { listDataSyncProviders } from "@/api/dataSync";

const garminSyncVisible = ref(false);

const allPrimaryItems = [
  { path: "/coach", title: "AI 教练", desc: "基于训练事实和科学规则获得只读建议。", icon: ChatDotRound },
  { path: "/runner-state", title: "训练状态", desc: "查看当前跑量趋势、训练执行和训练压力信号。", icon: TrendCharts },
  { path: "/todos", title: "待办中心", desc: "处理缺少感受、待确认活动和周复盘。", icon: Bell },
  { path: "/data-sync", title: "数据同步", desc: "连接运动平台并同步跑步活动", icon: Connection },
  { path: "/data-management", title: "数据管理", desc: "导入课表、补录训练和查看导入历史。", icon: FolderOpened },
  { path: "/feedback", title: "反馈", desc: "提交问题或使用建议", icon: Message },
  { path: "/my", title: "设置", desc: "账号和使用偏好入口。", icon: Setting },
];

const primaryItems = computed(() => allPrimaryItems.filter((item) => item.path !== "/data-sync" || garminSyncVisible.value));

const advancedItems = [
  { path: "/training-plan", title: "训练计划中心", icon: List },
  { path: "/weekly-review", title: "智能周复盘", icon: Memo },
  { path: "/dashboard", title: "训练统计", icon: DataAnalysis },
  { path: "/training-readiness", title: "负荷与恢复", icon: TrendCharts },
  { path: "/plan-imports", title: "课表导入", icon: DocumentAdd },
  { path: "/workout-import", title: "训练记录导入", icon: DocumentAdd },
  { path: "/ai-coach-preference", title: "AI 教练偏好", icon: Setting },
  { path: "/cycles", title: "训练周期", icon: Calendar },
  { path: "/blocks", title: "训练块", icon: Grid },
  { path: "/pace-rules", title: "配速规则", icon: TrendCharts },
];

function myEntryLink(path: string) {
  return { path, query: { from: "/my" } };
}

onMounted(async () => {
  try {
    await listDataSyncProviders(true);
    garminSyncVisible.value = true;
  } catch {
    garminSyncVisible.value = false;
  }
});
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
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
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
