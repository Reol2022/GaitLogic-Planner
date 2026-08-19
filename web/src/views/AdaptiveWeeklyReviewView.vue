<template>
  <div class="page-stack adaptive-review-page">
    <PageHeader title="周复盘与自适应调整" subtitle="确定性事实负责边界，AI 负责解释，计划修改必须由你确认。" />
    <section class="panel controls">
      <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="周开始" end-placeholder="周结束" />
      <el-button type="primary" :loading="loading" :disabled="!range" @click="generate">生成周复盘</el-button>
    </section>
    <el-alert title="AI 周复盘不是医疗建议，也不会自动修改训练计划。" type="info" :closable="false" show-icon />

    <WeeklyFactsPanel v-if="review" :facts="review.weekly_facts" />

    <section v-if="review" class="panel narrative">
      <header><h2>AI 周复盘</h2><el-tag v-if="review.fallback_used" type="warning">确定性降级结果</el-tag></header>
      <p class="overview">{{ review.overview }}</p>
      <div class="review-grid">
        <article><h3>完成情况</h3><p>{{ review.completion_summary }}</p></article>
        <article><h3>关键训练</h3><p>{{ review.key_session_summary }}</p></article>
        <article><h3>计划偏差</h3><p>{{ review.deviation_summary }}</p></article>
        <article><h3>疲劳与风险</h3><p>{{ review.fatigue_and_risk }}</p></article>
      </div>
      <el-alert v-for="warning in review.warnings" :key="warning" :title="warning" type="warning" :closable="false" show-icon />
      <div v-if="review.next_week_focus.length"><h3>下周关注点</h3><ul><li v-for="item in review.next_week_focus" :key="item">{{ item }}</li></ul></div>
      <el-collapse v-if="review.knowledge_references.length || review.limitations.length">
        <el-collapse-item title="知识依据与数据限制" name="references">
          <article v-for="item in review.knowledge_references" :key="`${item.document_id}-${item.section}`" class="reference">
            <strong>{{ item.title }} · {{ item.section }}</strong><p>{{ item.excerpt }}</p><small>{{ item.source_title }} · {{ item.knowledge_version }}</small>
          </article>
          <ul><li v-for="item in review.limitations" :key="item">{{ limitationMessage(item) }}</li></ul>
        </el-collapse-item>
      </el-collapse>
    </section>

    <AdaptiveProposalDiff v-if="proposal" :proposal="proposal" @approve="approve" @reject="reject" />
    <el-empty v-if="!loading && !review" description="选择一周后生成可解释周复盘" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import AdaptiveProposalDiff from "@/components/weekly-review/AdaptiveProposalDiff.vue";
import WeeklyFactsPanel from "@/components/weekly-review/WeeklyFactsPanel.vue";
import {
  approveAdaptiveProposal,
  generateLangGraphWeeklyReview,
  getAdaptiveProposal,
  rejectAdaptiveProposal,
} from "@/api/adaptivePlan";
import type { AdaptiveProposal, LangGraphWeeklyReview } from "@/types/adaptivePlan";
import { limitationMessage } from "@/utils/limitationDisplay";

const route = useRoute();
const range = ref<[string, string] | null>(null);
const review = ref<LangGraphWeeklyReview | null>(null);
const proposal = ref<AdaptiveProposal | null>(null);
const loading = ref(false);

function currentWeek(): [string, string] {
  const today = new Date();
  const day = (today.getDay() + 6) % 7;
  const start = new Date(today);
  start.setDate(today.getDate() - day);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const text = (value: Date) => value.toISOString().slice(0, 10);
  return [text(start), text(end)];
}

async function generate() {
  if (!range.value) return;
  loading.value = true;
  try {
    review.value = await generateLangGraphWeeklyReview({
      week_start: range.value[0],
      week_end: range.value[1],
      timezone: "Asia/Shanghai",
    });
    proposal.value = review.value.proposal_record_id
      ? await getAdaptiveProposal(review.value.proposal_record_id)
      : null;
  } finally {
    loading.value = false;
  }
}

async function approve() {
  if (!proposal.value) return;
  await ElMessageBox.confirm("确认后服务端会重新校验并创建新计划版本。是否继续？", "确认计划调整", { type: "warning" });
  const result = await approveAdaptiveProposal(proposal.value.id);
  proposal.value = await getAdaptiveProposal(proposal.value.id);
  ElMessage.success(result.duplicate ? "该 Proposal 已处理，本次未重复写入" : "新计划版本已创建");
}

async function reject() {
  if (!proposal.value) return;
  await ElMessageBox.confirm("拒绝后原计划保持不变。", "拒绝调整", { type: "warning" });
  await rejectAdaptiveProposal(proposal.value.id);
  proposal.value = await getAdaptiveProposal(proposal.value.id);
  ElMessage.success("已拒绝 Proposal，原计划未修改");
}

onMounted(async () => {
  range.value = currentWeek();
  const proposalId = Number(route.query.proposal_id);
  if (Number.isInteger(proposalId) && proposalId > 0) {
    proposal.value = await getAdaptiveProposal(proposalId);
  }
});
</script>

<style scoped>
.adaptive-review-page{gap:16px}.controls{display:flex;align-items:center;gap:12px;padding:16px}.narrative{padding:18px}.narrative header{display:flex;justify-content:space-between;align-items:center}.narrative h2{margin:0}.overview{font-size:15px;line-height:1.8}.review-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.review-grid article,.reference{padding:13px;border:1px solid var(--card-border);border-radius:10px}.review-grid h3{margin:0}.review-grid p,.reference p{line-height:1.7}.narrative :deep(.el-alert){margin-top:10px}.reference{margin-bottom:10px}.reference small{color:var(--muted)}@media(max-width:600px){.controls{align-items:stretch;flex-direction:column}.controls :deep(.el-date-editor){width:100%}.review-grid{grid-template-columns:1fr}}
</style>
