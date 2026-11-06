<template>
  <div class="page-stack adaptive-review-page">
    <PageHeader title="本周复盘与下周安排" subtitle="先看执行事实，再讨论调整；正式计划只在你明确确认后改变。" />
    <TrainingJourney active="review" />
    <section class="panel controls">
      <el-select v-model="cycleId" placeholder="训练周期" @change="loadBlocks"><el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" /></el-select>
      <el-select v-model="sourceBlockId" placeholder="复盘训练周" @change="chooseTarget"><el-option v-for="block in blocks" :key="block.id" :label="block.block_name" :value="block.id" /></el-select>
      <el-select v-model="targetBlockId" placeholder="下一训练周"><el-option v-for="block in targetBlocks" :key="block.id" :label="block.block_name" :value="block.id" /></el-select>
      <el-select v-if="history.length" v-model="selectedHistoryId" placeholder="历史周复盘" @change="loadHistoricalReview">
        <el-option v-for="item in history" :key="item.id" :label="`第 ${item.version} 版 · ${formatDateTime(item.created_at)}`" :value="item.id" />
      </el-select>
      <el-button type="primary" :loading="loading" :disabled="!range || !cycleId || !sourceBlockId || !targetBlockId" @click="generate">生成复盘与调整草稿</el-button>
    </section>
    <el-alert title="AI 周复盘不是医疗建议，也不会自动修改训练计划。" type="info" :closable="false" show-icon />
    <el-alert v-if="pageError" :title="pageError" type="error" :closable="false" show-icon />
    <p v-if="range && !targetBlockId" class="review-help">本周执行情况仍可查看。当前生成流程还需要选择下一训练周；可先在计划工具中完善安排，或与教练讨论。</p>
    <nav class="experience-links"><router-link to="/training-plan">返回计划</router-link><router-link to="/blocks">管理训练周</router-link><router-link :to="coachEntry('week', range?.[0])">和教练讨论这一周</router-link></nav>

    <el-skeleton v-if="factsLoading" class="panel facts-loading" :rows="3" animated />
    <section v-else-if="summary" class="panel execution-summary">
      <header class="section-heading">
        <div><h2>本周训练情况</h2><span>{{ summary.metrics.week_start_date }} 至 {{ summary.metrics.week_end_date }}</span></div>
        <span>日志覆盖率 {{ percent(summary.metrics.logged_workout_ratio) }}</span>
      </header>
      <div class="overview-metrics">
        <div><span>计划跑量</span><strong>{{ km(summary.metrics.planned_distance_km) }}</strong></div>
        <div><span>实际跑量</span><strong>{{ km(summary.metrics.actual_distance_km) }}</strong></div>
        <div><span>跑量完成比（整周）</span><strong>{{ percent(summary.metrics.completion_rate) }}</strong></div>
        <div><span>已完成 / 计划课程</span><strong>{{ summary.metrics.completed_workout_days }}/{{ summary.metrics.planned_workout_days }}</strong></div>
      </div>
      <p class="review-help">跑量完成比 = 实际跑量 ÷ 整周计划跑量，不等于到期课程完成率。未来安排、未同步或未关联活动不应直接判断为漏练。</p>
      <details><summary>展开每天的计划与实际</summary><div class="daily-review-grid">
        <article v-for="day in summary.metrics.daily_workouts" :key="day.planned_workout_id" class="daily-review-card">
          <div><strong>{{ day.date || "未定日期" }}</strong><el-tag size="small" effect="plain">{{ statusLabel(day.status) }}</el-tag></div>
          <p>{{ day.planned_content }}</p>
          <span>计划 {{ km(day.planned_distance_km) }} · 实际 {{ km(day.actual_distance_km) }} · RPE {{ day.rpe ?? "-" }}</span>
        </article>
      </div></details>
      <div class="completion-notes">
        <p><strong>关键课：</strong>{{ summary.metrics.key_workouts.length }} 次，平均 RPE {{ summary.metrics.key_workout_avg_rpe ?? "-" }}</p>
        <p><strong>长距离：</strong>{{ summary.metrics.long_run ? "已纳入复盘" : "本周无长距离计划" }}</p>
        <p><strong>数据缺失：</strong>{{ missingDataText }}</p>
      </div>
    </section>

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

    <section v-if="proposal" class="proposal-meta">
      <el-tag effect="plain">方案 v{{ proposal.revision || 1 }} / {{ maxProposalVersion }}</el-tag>
      <span v-if="proposal.parent_proposal_id">上一版方案已拒绝，当前为基于反馈生成的新方案。</span>
    </section>

    <section v-else-if="legacyReview" class="panel narrative">
      <header><h2>AI 周复盘</h2><el-tag effect="plain">历史记录</el-tag></header>
      <p class="overview">{{ legacyReview.report.summary || "该历史复盘未保存文字总结。" }}</p>
      <div class="review-grid">
        <article><h3>做得好的地方</h3><ul><li v-for="item in legacyReview.report.positive_points_json || []" :key="item">{{ item }}</li></ul></article>
        <article><h3>需要注意</h3><ul><li v-for="item in legacyReview.report.attention_points_json || []" :key="item">{{ item }}</li></ul></article>
      </div>
      <article v-if="legacyReview.report.next_week_strategy" class="strategy-card"><h3>下一周总体策略</h3><p>{{ legacyReview.report.next_week_strategy }}</p></article>
      <el-alert v-for="item in legacyReview.report.risk_notes_json || []" :key="item" :title="item" type="warning" :closable="false" show-icon />
    </section>
    <AdaptiveProposalDiff v-if="proposal" :proposal="proposal" @approve="approve" @reject="reject" />
    <el-button v-if="proposal?.status === 'pending_approval'" :disabled="!proposal.review_report_id" @click="feedbackVisible = true">反馈后重新生成方案</el-button>
    <el-dialog v-model="feedbackVisible" title="反馈并重新生成方案" width="560px">
      <p>反馈只表达你的偏好；系统仍会重新执行当前安全校验，不会绕过恢复、负荷和计划版本限制。</p>
      <el-checkbox-group v-model="feedback.reason_codes">
        <el-checkbox v-for="item in feedbackOptions" :key="item.value" :label="item.value">{{ item.label }}</el-checkbox>
      </el-checkbox-group>
      <el-input v-model="feedback.free_text" class="feedback-text" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="补充时间安排或偏好（可选）" />
      <template #footer><el-button @click="feedbackVisible = false">取消</el-button><el-button type="primary" :loading="revising" @click="revise">提交反馈并生成</el-button></template>
    </el-dialog>
    <el-empty v-if="!loading && !factsLoading && !review && !legacyReview && !summary" description="选择训练周期和训练周后，先查看实际完成情况。没有计划时仍可查看设备活动。" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import AdaptiveProposalDiff from "@/components/weekly-review/AdaptiveProposalDiff.vue";
import {
  approveAdaptiveProposal,
  generateLangGraphWeeklyReview,
  getAdaptiveProposal,
  rejectAdaptiveProposal,
  reviseAdaptiveProposal,
} from "@/api/adaptivePlan";
import type { AdaptiveProposal, LangGraphWeeklyReview } from "@/types/adaptivePlan";
import { limitationMessage } from "@/utils/limitationDisplay";
import TrainingJourney from "@/components/common/TrainingJourney.vue";
import { coachEntry, localDate } from "@/utils/coreExperience";
import { getActiveTrainingCycle, listTrainingCycles } from "@/api/trainingCycles";
import { listTrainingBlocks } from "@/api/trainingBlocks";
import { getWeeklyReview, getWeeklyReviewSummary, listWeeklyReviews } from "@/api/weeklyReviews";
import type { TrainingBlock, TrainingCycle, WeeklyReviewDetail, WeeklyReviewReport, WeeklyReviewSummary } from "@/types/models";

const route = useRoute();
const cycleId = ref<number | null>(Number(route.query.cycle_id) || null);
const sourceBlockId = ref<number | null>(Number(route.query.source_block_id) || null);
const targetBlockId = ref<number | null>(Number(route.query.target_block_id) || null);
const cycles = ref<TrainingCycle[]>([]);
const blocks = ref<TrainingBlock[]>([]);
const targetBlocks = computed(() => blocks.value.filter((item) => item.id !== sourceBlockId.value));
const range = ref<[string, string] | null>(null);
const review = ref<LangGraphWeeklyReview | null>(null);
const summary = ref<WeeklyReviewSummary | null>(null);
const history = ref<WeeklyReviewReport[]>([]);
const selectedHistoryId = ref<number | null>(null);
const legacyReview = ref<WeeklyReviewDetail | null>(null);
const proposal = ref<AdaptiveProposal | null>(null);
const loading = ref(false);
const factsLoading = ref(false);
const pageError = ref('');
let factsRequest = 0;
let blockRequest = 0;
let historyRequest = 0;
const revising = ref(false);
const feedbackVisible = ref(false);
const maxProposalVersion = ref(3);
const feedback = ref<{ reason_codes: string[]; free_text: string }>({ reason_codes: [], free_text: "" });
const feedbackOptions = [
  { value: "VOLUME_TOO_HIGH", label: "跑量偏高" }, { value: "VOLUME_TOO_LOW", label: "跑量偏低" },
  { value: "TOO_MANY_QUALITY_SESSIONS", label: "强度课过多" }, { value: "WORKOUT_DAY_CONFLICT", label: "训练日冲突" },
  { value: "LONG_RUN_CONFLICT", label: "长距离安排冲突" }, { value: "INSUFFICIENT_RECOVERY", label: "恢复不足" },
  { value: "PERSONAL_SCHEDULE_CONFLICT", label: "个人日程冲突" }, { value: "OTHER", label: "其他" },
];

function currentWeek(): [string, string] {
  const today = new Date();
  const day = (today.getDay() + 6) % 7;
  const start = new Date(today);
  start.setDate(today.getDate() - day);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const text = localDate;
  return [text(start), text(end)];
}

async function loadBlocks() {
  const request = ++blockRequest;
  ++factsRequest;
  summary.value = null; review.value = null; proposal.value = null; legacyReview.value = null;
  const rows = cycleId.value ? await listTrainingBlocks(cycleId.value) : [];
  if (request !== blockRequest) return;
  blocks.value = rows;
  const today = localDate();
  sourceBlockId.value = blocks.value.find(item => item.id === sourceBlockId.value)?.id
    || blocks.value.find(item => item.start_date && item.end_date && item.start_date <= today && item.end_date >= today)?.id
    || [...blocks.value].reverse().find(item => item.end_date && item.end_date < today)?.id
    || blocks.value[0]?.id || null;
  chooseTarget();
}

function chooseTarget() {
  review.value = null;
  proposal.value = null;
  const index = blocks.value.findIndex((item) => item.id === sourceBlockId.value);
  targetBlockId.value = index >= 0 ? blocks.value[index + 1]?.id || null : null;
  const source = blocks.value.find((item) => item.id === sourceBlockId.value);
  if (source?.start_date && source.end_date) range.value = [source.start_date, source.end_date];
  else range.value = null;
  void loadFacts();
}

async function loadFacts() {
  const request = ++factsRequest;
  ++historyRequest;
  factsLoading.value = false;
  summary.value = null;
  history.value = [];
  selectedHistoryId.value = null;
  legacyReview.value = null;
  if (!range.value || !cycleId.value || !sourceBlockId.value) return;
  factsLoading.value = true;
  pageError.value = '';
  try {
    const [summaryResult, historyResult] = await Promise.all([
      getWeeklyReviewSummary(cycleId.value, sourceBlockId.value),
      listWeeklyReviews(cycleId.value),
    ]);
    if (request !== factsRequest) return;
    summary.value = summaryResult;
    history.value = historyResult.items.filter((item) => (
      item.source_block_id === sourceBlockId.value
      && item.status === "success"
      && Boolean(item.summary)
    ));
    selectedHistoryId.value = history.value[0]?.id || null;
    await loadHistoricalReview();
  } catch {
    if (request === factsRequest) pageError.value = '本周训练情况加载失败，请重新选择训练周重试。未加载不代表没有训练。';
  } finally {
    if (request === factsRequest) factsLoading.value = false;
  }
}

async function loadHistoricalReview() {
  const request = ++historyRequest;
  const id = selectedHistoryId.value;
  review.value = null;
  proposal.value = null;
  legacyReview.value = null;
  const result = id ? await getWeeklyReview(id) : null;
  if (request === historyRequest && id === selectedHistoryId.value) legacyReview.value = result;
}

async function generate() {
  if (loading.value) return;
  if (!range.value || !cycleId.value || !sourceBlockId.value || !targetBlockId.value) return;
  loading.value = true;
  pageError.value = '';
  const requestedSelection = `${cycleId.value}:${sourceBlockId.value}:${targetBlockId.value}`;
  try {
    const generated = await generateLangGraphWeeklyReview({
      week_start: range.value[0],
      week_end: range.value[1],
      cycle_id: cycleId.value,
      source_block_id: sourceBlockId.value,
      target_block_id: targetBlockId.value,
      timezone: "Asia/Shanghai",
    });
    if (requestedSelection !== `${cycleId.value}:${sourceBlockId.value}:${targetBlockId.value}`) return;
    review.value = generated;
    proposal.value = review.value.proposal_record_id
      ? await getAdaptiveProposal(review.value.proposal_record_id)
      : null;
  } catch {
    pageError.value = '复盘未能完成，正式计划没有因此改变。请稍后重试。';
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
  ElMessage.success("已保留原计划，不采用本次调整");
}

function km(value?: number | null) { return `${Number(value || 0).toFixed(1)} km`; }
function percent(value?: number | null) { return `${Math.round(Number(value || 0) * 100)}%`; }
function statusLabel(value: string) {
  return ({
    completed_high: "高质量完成", completed_normal: "完成", completed_adjusted: "降级完成",
    missed: "未完成", skipped: "跳过", rest: "休息", rest_or_cancelled: "休息", not_started: "未开始",
  } as Record<string, string>)[value] || value;
}
function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}
const missingDataText = computed(() => summary.value?.metrics.missing_fields.length
  ? summary.value.metrics.missing_fields.join("、")
  : "核心字段已记录");

async function revise() {
  if (!proposal.value?.review_report_id) return;
  if (!feedback.value.reason_codes.length && !feedback.value.free_text.trim()) {
    ElMessage.warning("请选择反馈原因或补充说明");
    return;
  }
  revising.value = true;
  try {
    const result = await reviseAdaptiveProposal(proposal.value.review_report_id, {
      proposal_id: proposal.value.id,
      feedback: { reason_codes: feedback.value.reason_codes, free_text: feedback.value.free_text.trim() || null },
    });
    if (result.status === "REVIEW_STALE") {
      ElMessage.error("本周训练事实已发生变化，当前周复盘已过期，请重新生成周复盘。");
      return;
    }
    if (result.status === "REVISION_LIMIT_REACHED") {
      ElMessage.warning("已达到当前周复盘的方案调整次数上限，可保留原计划或重新生成新的周复盘。");
      return;
    }
    proposal.value = result.proposal || null;
    maxProposalVersion.value = result.revision_limit + 1;
    feedbackVisible.value = false;
    feedback.value = { reason_codes: [], free_text: "" };
    ElMessage.success("已根据反馈生成新的调整方案");
  } finally { revising.value = false; }
}

onMounted(async () => {
  range.value = currentWeek();
  cycles.value = await listTrainingCycles();
  if (!cycleId.value) {
    try { cycleId.value = (await getActiveTrainingCycle()).id; } catch { cycleId.value = null; }
  }
  if (cycleId.value) await loadBlocks();
  const proposalId = Number(route.query.proposal_id);
  if (Number.isInteger(proposalId) && proposalId > 0) {
    proposal.value = await getAdaptiveProposal(proposalId);
  }
});
</script>

<style scoped>
.controls{flex-wrap:wrap}.review-help{color:var(--muted);font-size:13px;line-height:1.7}.execution-summary summary{cursor:pointer;padding:12px 0;color:var(--muted)}
.adaptive-review-page{gap:16px}.controls{display:flex;align-items:center;gap:12px;padding:16px}.narrative,.execution-summary{padding:18px}.narrative header,.proposal-meta,.section-heading{display:flex;justify-content:space-between;align-items:center;gap:10px}.narrative h2,.section-heading h2{margin:0}.section-heading span{color:var(--muted);font-size:12px}.overview{font-size:15px;line-height:1.8}.review-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.review-grid article,.reference,.daily-review-card{padding:13px;border:1px solid var(--card-border);border-radius:10px}.review-grid h3{margin:0}.review-grid p,.reference p{line-height:1.7}.narrative :deep(.el-alert){margin-top:10px}.reference{margin-bottom:10px}.reference small{color:var(--muted)}.overview-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}.overview-metrics div,.completion-notes p{padding:12px;background:var(--surface-muted);border-radius:10px}.overview-metrics span{display:block;color:var(--muted);font-size:12px}.overview-metrics strong{display:block;margin-top:6px}.daily-review-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.daily-review-card>div{display:flex;align-items:center;justify-content:space-between;gap:10px}.daily-review-card p{margin:10px 0;line-height:1.55}.daily-review-card>span{color:var(--muted);font-size:12px}.completion-notes{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.completion-notes p{margin:0}.feedback-text{margin-top:14px}@media(max-width:600px){.controls{align-items:stretch;flex-direction:column}.controls :deep(.el-date-editor){width:100%}.review-grid,.daily-review-grid{grid-template-columns:1fr}.overview-metrics{grid-template-columns:repeat(2,1fr)}.completion-notes{grid-template-columns:1fr}.proposal-meta{align-items:flex-start;flex-direction:column}}
</style>
