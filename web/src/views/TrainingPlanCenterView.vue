<template>
  <div class="page-stack training-plan-page">
    <PageHeader title="训练计划" subtitle="默认展示当前正在进行的训练周期。" />

    <section v-if="!loading && !overview?.has_active_cycle" class="empty-panel">
      <div>
        <strong>当前没有生效中的训练周期</strong>
        <p>可以保留多个草稿周期，但首页、今日训练和计划中心只读取唯一 active 周期。</p>
      </div>
      <el-button type="primary" @click="router.push('/cycles')">去启用周期</el-button>
    </section>

    <template v-else>
      <section class="plan-hero" v-loading="loading">
        <div>
          <span class="eyebrow">当前周期</span>
          <h2>{{ overview?.active_cycle?.name || "读取中" }}</h2>
          <p>
            {{ dateRangeText }}
            <span v-if="overview?.current_block"> · {{ String(overview.current_block.name || "当前训练块") }}</span>
          </p>
        </div>
        <div class="hero-actions">
          <el-button type="primary" @click="router.push('/workouts')">查看计划</el-button>
          <el-button plain @click="router.push('/training-calendar')">训练日历</el-button>
        </div>
      </section>

      <section class="week-panel">
        <div class="section-head">
          <div>
            <strong>本周安排</strong>
            <span>{{ overview?.week_start }} 至 {{ overview?.week_end }}</span>
          </div>
          <el-button text @click="router.push('/workouts')">全部计划</el-button>
        </div>
        <div class="week-list">
          <article v-for="item in overview?.week_workouts || []" :key="item.id" class="week-item">
            <div class="week-date">
              <strong>{{ dayText(item.workout_date) }}</strong>
              <span>{{ item.weekday || "-" }}</span>
            </div>
            <div class="week-main">
              <p>{{ item.planned_content }}</p>
              <span>{{ item.planned_distance_km || 0 }} km · {{ item.target_pace_text || "配速按体感执行" }}</span>
            </div>
            <el-tag effect="plain">{{ statusLabel(item.workout_log?.status_normalized || "not_started") }}</el-tag>
          </article>
          <el-empty v-if="!loading && (overview?.week_workouts || []).length === 0" description="本周暂无训练安排" />
        </div>
      </section>

      <section class="action-grid">
        <button v-for="action in overview?.primary_actions || []" :key="action.path" type="button" @click="router.push(action.path)">
          <el-icon><ArrowRight /></el-icon>
          <span>{{ action.label }}</span>
        </button>
      </section>

      <section class="panel advanced-panel">
        <el-collapse>
          <el-collapse-item title="高级计划工具" name="advanced">
            <div class="advanced-grid">
              <router-link v-for="link in overview?.advanced_links || []" :key="link.path" :to="link.path">
                {{ link.label }}
              </router-link>
            </div>
          </el-collapse-item>
        </el-collapse>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ArrowRight } from "@element-plus/icons-vue";
import { getTrainingPlanOverview } from "@/api/simplifiedWorkflow";
import type { TrainingPlanOverview } from "@/types/models";
import { statusLabel } from "@/utils/statusLabels";

const router = useRouter();
const loading = ref(false);
const overview = ref<TrainingPlanOverview | null>(null);

const dateRangeText = computed(() => {
  const cycle = overview.value?.active_cycle;
  if (!cycle) return "";
  return `${cycle.actual_start_date || cycle.start_date || "-"} 至 ${cycle.actual_end_date || cycle.end_date || "进行中"}`;
});

function dayText(value?: string | null) {
  if (!value) return "-";
  return value.slice(5);
}

async function load() {
  loading.value = true;
  try {
    overview.value = await getTrainingPlanOverview();
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.training-plan-page {
  gap: 14px;
}

.empty-panel,
.plan-hero,
.week-panel {
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.empty-panel,
.plan-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px;
}

.empty-panel strong,
.plan-hero h2,
.section-head strong {
  color: #172033;
}

.empty-panel p,
.plan-hero p,
.section-head span,
.week-main span {
  color: #667085;
}

.plan-hero h2 {
  margin: 4px 0;
  font-size: 24px;
}

.eyebrow {
  color: #1976d2;
  font-size: 12px;
  font-weight: 700;
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.week-panel {
  padding: 16px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.section-head > div {
  display: grid;
  gap: 2px;
}

.week-list {
  display: grid;
  gap: 8px;
}

.week-item {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e4e7ec;
  border-radius: 6px;
  background: #fbfcfd;
}

.week-date {
  display: grid;
  gap: 2px;
}

.week-date strong {
  color: #172033;
}

.week-date span {
  color: #667085;
  font-size: 12px;
}

.week-main {
  min-width: 0;
}

.week-main p {
  overflow: hidden;
  margin: 0 0 5px;
  color: #172033;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.action-grid button,
.advanced-grid a {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #d8dde3;
  border-radius: 6px;
  background: #ffffff;
  color: #172033;
  font: inherit;
  text-decoration: none;
  cursor: pointer;
}

.action-grid button .el-icon {
  color: #1976d2;
}

.advanced-panel {
  padding: 0 16px;
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding-bottom: 14px;
}

@media (max-width: 768px) {
  .training-plan-page {
    padding: 14px;
  }

  .empty-panel,
  .plan-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .hero-actions {
    width: 100%;
  }

  .hero-actions .el-button {
    flex: 1;
  }

  .week-item {
    grid-template-columns: 58px minmax(0, 1fr);
  }

  .week-item .el-tag {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .action-grid,
  .advanced-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
