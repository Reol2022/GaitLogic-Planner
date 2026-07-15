<template>
  <div class="page-stack task-center-page">
    <PageHeader title="待办中心" subtitle="只保留需要你处理的训练闭环事项。" />

    <section class="summary-strip">
      <div>
        <strong>{{ tasks.length }}</strong>
        <span>待处理</span>
      </div>
      <div>
        <strong>{{ highPriorityCount }}</strong>
        <span>优先处理</span>
      </div>
      <div>
        <strong>{{ subjectiveCount }}</strong>
        <span>训练感受待补</span>
      </div>
    </section>

    <section class="task-list" v-loading="loading">
      <article v-for="task in tasks" :key="task.task_key" class="task-row">
        <div class="task-icon">
          <el-icon><component :is="iconFor(task.task_type)" /></el-icon>
        </div>
        <div class="task-main">
          <div class="task-title">
            <strong>{{ task.title }}</strong>
            <el-tag v-if="task.count > 1" size="small" effect="plain">{{ task.count }} 项</el-tag>
          </div>
          <p>{{ task.description || "无需额外说明。" }}</p>
        </div>
        <div class="task-actions">
          <el-button type="primary" size="small" @click="goTask(task)">处理</el-button>
          <el-button size="small" text @click="dismissTask(task.task_key)">忽略</el-button>
        </div>
      </article>

      <el-empty v-if="!loading && tasks.length === 0" description="今天没有需要处理的事项">
        <el-button type="primary" @click="router.push('/today')">回到今日训练</el-button>
      </el-empty>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Bell, Calendar, CircleCheck, Connection, EditPen, Warning } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { completeTodo, getTodos } from "@/api/simplifiedWorkflow";
import type { TaskItem } from "@/types/models";

const router = useRouter();
const loading = ref(false);
const tasks = ref<TaskItem[]>([]);

const highPriorityCount = computed(() => tasks.value.filter((task) => task.priority <= 30).length);
const subjectiveCount = computed(() => tasks.value.filter((task) => task.task_type === "subjective_data_missing").length);

function iconFor(taskType: string) {
  if (taskType === "subjective_data_missing") return EditPen;
  if (taskType === "activity_needs_review" || taskType === "sync_failed") return Warning;
  if (taskType === "provider_reauthentication_required") return Connection;
  if (taskType === "weekly_review_ready" || taskType === "cycle_ending_soon") return Calendar;
  if (taskType === "plan_adjustment_ready") return Bell;
  return CircleCheck;
}

function goTask(task: TaskItem) {
  router.push(task.action_path || "/today");
}

async function dismissTask(taskKey: string) {
  const response = await completeTodo(taskKey);
  tasks.value = response.items;
  ElMessage.success("已从当前列表移除");
}

async function load() {
  loading.value = true;
  try {
    const response = await getTodos();
    tasks.value = response.items;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.task-center-page {
  gap: 14px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.summary-strip > div {
  display: grid;
  gap: 2px;
  padding: 14px 16px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.summary-strip strong {
  color: #172033;
  font-size: 24px;
}

.summary-strip span,
.task-main p {
  color: #667085;
  font-size: 13px;
}

.task-list {
  display: grid;
  gap: 10px;
}

.task-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.task-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #edf5ff;
  color: #1976d2;
  font-size: 20px;
}

.task-main {
  min-width: 0;
}

.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.task-title strong {
  overflow: hidden;
  color: #172033;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-main p {
  margin: 5px 0 0;
  line-height: 1.5;
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 768px) {
  .task-center-page {
    padding: 14px;
  }

  .summary-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .summary-strip > div {
    padding: 12px 10px;
  }

  .summary-strip strong {
    font-size: 20px;
  }

  .task-row {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .task-actions {
    grid-column: 1 / -1;
    justify-content: flex-end;
  }
}
</style>
