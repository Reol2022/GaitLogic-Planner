<template>
  <div class="page-stack rule-governance-page">
    <PageHeader title="科学规则治理" subtitle="管理训练规则的证据、版本、测试覆盖率和运行质量。" />

    <section class="metric-grid">
      <article class="metric-card">
        <span>已发布规则</span>
        <strong>{{ coverage?.published_rules ?? "-" }}</strong>
      </article>
      <article class="metric-card">
        <span>Positive 覆盖</span>
        <strong>{{ coverage?.rules_with_positive_case ?? "-" }}</strong>
      </article>
      <article class="metric-card">
        <span>Negative 覆盖</span>
        <strong>{{ coverage?.rules_with_negative_case ?? "-" }}</strong>
      </article>
      <article class="metric-card">
        <span>未覆盖</span>
        <strong>{{ coverage?.uncovered_rules.length ?? "-" }}</strong>
      </article>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">回归测试</h2>
        <el-button type="primary" :loading="running" @click="runRegression">运行回归</el-button>
      </div>
      <el-table :data="testRuns" size="small" empty-text="暂无测试运行记录">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="run_type" label="类型" width="120" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="total_cases" label="案例" width="90" />
        <el-table-column prop="passed_cases" label="通过" width="90" />
        <el-table-column prop="failed_cases" label="失败" width="90" />
        <el-table-column label="完成时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.finished_at || row.started_at) }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">证据来源</h2>
      </div>
      <el-table :data="evidence" size="small" empty-text="暂无证据来源">
        <el-table-column prop="code" label="Code" min-width="220" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="source_type" label="类型" width="160" />
        <el-table-column prop="evidence_level" label="等级" width="150" />
        <el-table-column prop="review_status" label="状态" width="120" />
      </el-table>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">运行质量</h2>
      </div>
      <div class="quality-grid">
        <article>
          <h3>Action 分布</h3>
          <p v-for="item in objectRows(metrics?.action_distribution)" :key="item.key">{{ item.key }}：{{ item.value }}</p>
        </article>
        <article>
          <h3>Context 分布</h3>
          <p v-for="item in objectRows(metrics?.context_distribution)" :key="item.key">{{ item.key }}：{{ item.value }}</p>
        </article>
        <article>
          <h3>状态计数</h3>
          <p v-for="item in objectRows(metrics?.status_counts)" :key="item.key">{{ item.key }}：{{ item.value }}</p>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  getRuleCoverage,
  getRuleMetrics,
  listRuleTestRuns,
  listTrainingEvidence,
  runRuleRegression,
  type EvidenceSource,
  type RuleCoverage,
  type RuleMetrics,
  type RuleTestRun,
} from "@/api/ruleGovernance";

const evidence = ref<EvidenceSource[]>([]);
const coverage = ref<RuleCoverage | null>(null);
const metrics = ref<RuleMetrics | null>(null);
const testRuns = ref<RuleTestRun[]>([]);
const running = ref(false);

function objectRows(value?: Record<string, number>) {
  return Object.entries(value || {}).map(([key, item]) => ({ key, value: item }));
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

async function load() {
  const [evidenceResult, coverageResult, metricsResult, runsResult] = await Promise.all([
    listTrainingEvidence(),
    getRuleCoverage(),
    getRuleMetrics(),
    listRuleTestRuns(),
  ]);
  evidence.value = evidenceResult;
  coverage.value = coverageResult;
  metrics.value = metricsResult;
  testRuns.value = runsResult;
}

async function runRegression() {
  running.value = true;
  try {
    const result = await runRuleRegression();
    ElMessage.success(`回归完成：${result.passed_cases}/${result.total_cases} 通过`);
    await load();
  } finally {
    running.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.metric-grid,
.quality-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card,
.quality-grid article {
  padding: 16px;
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  background: #ffffff;
  box-shadow: var(--card-shadow);
}

.metric-card span {
  color: var(--muted);
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin-top: 6px;
  color: var(--text);
  font-size: 24px;
}

.quality-grid article {
  min-height: 120px;
}

.quality-grid h3 {
  margin: 0 0 10px;
  font-size: 15px;
}

.quality-grid p {
  margin: 6px 0;
  color: var(--muted);
  font-size: 13px;
}

@media (max-width: 900px) {
  .metric-grid,
  .quality-grid {
    grid-template-columns: 1fr;
  }
}
</style>
