<template>
  <div class="page-stack weekly-review-page">
    <PageHeader title="智能周复盘" subtitle="基于真实执行记录复盘本周，并在你确认后调整下一周计划。" />

    <div class="toolbar review-toolbar">
      <div class="filter-row">
        <el-select v-model="cycleId" placeholder="训练周期" @change="handleCycleChange">
          <el-option v-for="cycle in cycles" :key="cycle.id" :label="cycle.name" :value="cycle.id" />
        </el-select>
        <el-select v-model="sourceBlockId" placeholder="复盘训练周" @change="handleSourceChange">
          <el-option v-for="block in blocks" :key="block.id" :label="block.block_name" :value="block.id" />
        </el-select>
        <el-select v-model="targetBlockId" clearable placeholder="下一训练周">
          <el-option v-for="block in targetBlocks" :key="block.id" :label="block.block_name" :value="block.id" />
        </el-select>
      </div>
      <el-button type="primary" :loading="generating" :disabled="!summary || !targetBlockId" @click="generate">
        {{ detail ? "重新生成复盘" : "生成复盘" }}
      </el-button>
    </div>

    <el-alert
      v-if="summary && !summary.metrics.is_week_complete"
      title="当前训练周尚未结束，可以提前查看统计，但建议训练周结束后再生成正式复盘。"
      type="warning"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="summary?.training_status.status === 'insufficient_data'"
      title="本周训练记录较少，系统只能提供基础统计。完成训练后填写日志，复盘会更准确。"
      type="info"
      :closable="false"
      show-icon
    />

    <template v-if="summary">
      <section>
        <div class="section-heading"><h2>本周概览</h2><span>{{ summary.metrics.week_start_date }} 至 {{ summary.metrics.week_end_date }}</span></div>
        <div class="review-metrics">
          <div v-for="metric in overviewMetrics" :key="metric.label" class="metric-card">
            <p class="metric-label">{{ metric.label }}</p>
            <div class="metric-value">{{ metric.value }}</div>
          </div>
        </div>
      </section>

      <section class="panel review-section">
        <div class="section-heading"><h2>完成情况</h2><span>日志覆盖率 {{ percent(summary.metrics.logged_workout_ratio) }}</span></div>
        <div class="daily-review-grid">
          <article v-for="day in summary.metrics.daily_workouts" :key="day.planned_workout_id" class="daily-review-card">
            <div><strong>{{ day.date || "未定日期" }}</strong><el-tag size="small" effect="plain">{{ statusLabel(day.status) }}</el-tag></div>
            <p>{{ day.planned_content }}</p>
            <span>计划 {{ km(day.planned_distance_km) }} · 实际 {{ km(day.actual_distance_km) }} · RPE {{ day.rpe ?? "-" }}</span>
          </article>
        </div>
        <div class="completion-notes">
          <p><strong>关键课：</strong>{{ summary.metrics.key_workouts.length }} 次，平均 RPE {{ summary.metrics.key_workout_avg_rpe ?? "-" }}</p>
          <p><strong>长距离：</strong>{{ summary.metrics.long_run ? "已纳入复盘" : "本周无长距离计划" }}</p>
          <p><strong>数据缺失：</strong>{{ missingDataText }}</p>
        </div>
      </section>

      <section class="panel review-section status-section">
        <div class="status-title">
          <el-tag :type="statusTagType" size="large" effect="light">{{ trainingStatusLabel }}</el-tag>
          <h2>训练状态</h2>
        </div>
        <ul><li v-for="reason in summary.training_status.reasons" :key="reason">{{ reason }}</li></ul>
        <p class="safety-note">该状态仅用于训练管理提示，不构成医疗诊断或受伤风险预测。</p>
      </section>
    </template>

    <section v-if="detail" class="panel review-section ai-review-section">
      <div class="section-heading">
        <h2>AI 周复盘</h2>
        <el-select v-if="history.length" v-model="selectedReviewId" size="small" @change="loadHistoryDetail">
          <el-option v-for="item in history" :key="item.id" :label="`第 ${item.version} 版 · ${formatDateTime(item.created_at)}`" :value="item.id" />
        </el-select>
      </div>
      <p class="review-summary">{{ detail.report.summary }}</p>
      <div class="review-copy-grid">
        <article><h3>做得好的地方</h3><ul><li v-for="item in detail.report.positive_points_json || []" :key="item">{{ item }}</li></ul></article>
        <article><h3>需要注意</h3><ul><li v-for="item in detail.report.attention_points_json || []" :key="item">{{ item }}</li></ul></article>
      </div>
      <article class="strategy-card"><h3>下一周总体策略</h3><p>{{ detail.report.next_week_strategy }}</p></article>
      <el-alert v-for="item in detail.report.risk_notes_json || []" :key="item" :title="item" type="warning" :closable="false" show-icon />
    </section>

    <section v-if="draft" class="panel review-section adjustment-section">
      <div class="section-heading">
        <div><h2>下一周调整对比</h2><span>原计划 {{ km(draft.original_week_distance_km) }} → 建议 {{ km(draft.suggested_week_distance_km) }}</span></div>
        <div class="selection-actions"><el-button text @click="setAll(true)">全选建议</el-button><el-button text @click="setAll(false)">取消全选</el-button></div>
      </div>
      <div class="adjustment-list">
        <article v-for="item in draft.items" :key="item.id" class="adjustment-card" :class="{ selected: item.is_selected }">
          <div class="adjustment-head">
            <div><strong>{{ item.workout_date || "未定日期" }}</strong><el-tag size="small">{{ actionLabel(item.action) }}</el-tag></div>
            <el-checkbox v-model="item.is_selected" :disabled="item.is_applied" @change="toggleItem(item)" >采用</el-checkbox>
          </div>
          <div class="plan-compare">
            <div><span>原计划</span><p>{{ item.original_content }}</p><small>{{ km(item.original_distance_km) }} · {{ mainTypeLabel(item.original_main_type) }} · {{ item.original_target_pace_text || "无配速" }}</small></div>
            <div class="suggested"><span>建议计划</span><p>{{ item.suggested_content }}</p><small>{{ km(item.suggested_distance_km) }} · {{ mainTypeLabel(item.suggested_main_type) }} · {{ item.suggested_target_pace_text || "无配速" }}</small></div>
          </div>
          <p class="adjustment-reason"><strong>调整原因：</strong>{{ item.reason }}</p>
          <el-button size="small" :disabled="item.is_applied" @click="openEdit(item)">编辑建议</el-button>
        </article>
      </div>
      <div class="draft-actions">
        <el-button :disabled="!canEditDraft" @click="rejectDraft">保留原计划</el-button>
        <el-button type="primary" :loading="applying" :disabled="!selectedItemIds.length || !canEditDraft" @click="applyDraft">应用已选择调整</el-button>
      </div>
    </section>

    <el-empty v-if="!loading && !summary" description="请选择训练周期和训练周查看复盘统计" />

    <div v-if="draft && canEditDraft" class="mobile-apply-bar">
      <span>已选 {{ selectedItemIds.length }} 项</span>
      <el-button type="primary" :disabled="!selectedItemIds.length" :loading="applying" @click="applyDraft">应用调整</el-button>
    </div>

    <el-dialog v-model="editVisible" title="编辑调整建议" width="560px">
      <el-form v-if="editForm" label-position="top">
        <el-form-item label="建议内容"><el-input v-model="editForm.suggested_content" type="textarea" :rows="3" /></el-form-item>
        <div class="edit-grid">
          <el-form-item label="建议距离 km"><el-input-number v-model="editForm.suggested_distance_km" :min="0" :precision="2" /></el-form-item>
          <el-form-item label="建议类型"><el-select v-model="editForm.suggested_main_type"><el-option v-for="option in mainTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <el-form-item label="建议配速"><el-input v-model="editForm.suggested_target_pace_text" placeholder="例如 4:30-4:40/km" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editVisible = false">取消</el-button><el-button type="primary" :loading="savingItem" @click="saveEdit">保存并重新校验</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { listTrainingCycles } from "@/api/trainingCycles";
import { listTrainingBlocks } from "@/api/trainingBlocks";
import { trackUsageEvent } from "@/api/usageEvents";
import {
  applyAdjustmentDraft,
  generateWeeklyReview,
  getWeeklyReview,
  getWeeklyReviewSummary,
  listWeeklyReviews,
  rejectAdjustmentDraft,
  updateAdjustmentItem,
} from "@/api/weeklyReviews";
import type { AdjustmentItem, TrainingBlock, TrainingCycle, WeeklyReviewDetail, WeeklyReviewReport, WeeklyReviewSummary, WorkoutMainTypeNormalized } from "@/types/models";
import { mainTypeOptions } from "@/types/options";

const route = useRoute();
const cycles = ref<TrainingCycle[]>([]);
const blocks = ref<TrainingBlock[]>([]);
const cycleId = ref<number | null>(Number(route.query.cycle_id) || null);
const sourceBlockId = ref<number | null>(Number(route.query.block_id) || null);
const targetBlockId = ref<number | null>(null);
const summary = ref<WeeklyReviewSummary | null>(null);
const detail = ref<WeeklyReviewDetail | null>(null);
const history = ref<WeeklyReviewReport[]>([]);
const selectedReviewId = ref<number | null>(null);
const loading = ref(false);
const generating = ref(false);
const applying = ref(false);
const savingItem = ref(false);
const editVisible = ref(false);
const editingItemId = ref<number | null>(null);
const editForm = reactive<{ suggested_content: string; suggested_distance_km: number; suggested_main_type: WorkoutMainTypeNormalized; suggested_target_pace_text: string }>({ suggested_content: "", suggested_distance_km: 0, suggested_main_type: "easy", suggested_target_pace_text: "" });

const targetBlocks = computed(() => blocks.value.filter((item) => item.id !== sourceBlockId.value));
const draft = computed(() => detail.value?.adjustment_draft || null);
const selectedItemIds = computed(() => draft.value?.items.filter((item) => item.is_selected && !item.is_applied).map((item) => item.id) || []);
const canEditDraft = computed(() => draft.value ? ["draft", "partially_applied"].includes(draft.value.status) : false);
const overviewMetrics = computed(() => summary.value ? [
  { label: "计划跑量", value: km(summary.value.metrics.planned_distance_km) },
  { label: "实际跑量", value: km(summary.value.metrics.actual_distance_km) },
  { label: "完成率", value: percent(summary.value.metrics.completion_rate) },
  { label: "完成天数", value: `${summary.value.metrics.completed_workout_days}/${summary.value.metrics.planned_workout_days}` },
  { label: "关键课完成", value: String(summary.value.metrics.key_workouts.filter((item) => String(item.status).startsWith("completed")).length) },
  { label: "平均 RPE", value: String(summary.value.metrics.avg_rpe ?? "-") },
  { label: "最大疼痛", value: String(summary.value.metrics.max_pain_level ?? "-") },
] : []);
const missingDataText = computed(() => summary.value?.metrics.missing_fields.length ? summary.value.metrics.missing_fields.join("、") : "核心字段已记录");
const statusTagType = computed(() => ({ normal: "success", watch: "warning", reduce_load: "danger", insufficient_data: "info" }[summary.value?.training_status.status || "insufficient_data"] as "success" | "warning" | "danger" | "info"));
const trainingStatusLabel = computed(() => ({ normal: "状态正常", watch: "关注恢复", reduce_load: "建议降负荷", insufficient_data: "数据不足" }[summary.value?.training_status.status || "insufficient_data"]));

function km(value?: number | null) { return `${Number(value || 0).toFixed(1)} km`; }
function percent(value?: number | null) { return `${Math.round(Number(value || 0) * 100)}%`; }
function statusLabel(value: string) { return ({ completed_high: "高质量完成", completed_normal: "完成", completed_adjusted: "降级完成", missed: "未完成", skipped: "跳过", rest: "休息", rest_or_cancelled: "休息", not_started: "未开始" } as Record<string, string>)[value] || value; }
function actionLabel(value: string) { return ({ keep: "保持", reduce: "减量", replace: "替换", rest: "休息" } as Record<string, string>)[value] || value; }
function mainTypeLabel(value?: string | null) { return mainTypeOptions.find((item) => item.value === value)?.label || value || "-"; }
function formatDateTime(value: string) { return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); }

async function handleCycleChange() {
  blocks.value = cycleId.value ? await listTrainingBlocks(cycleId.value) : [];
  sourceBlockId.value = blocks.value[blocks.value.length - 1]?.id || null;
  chooseTarget();
  await loadPage();
}
function chooseTarget() {
  const index = blocks.value.findIndex((item) => item.id === sourceBlockId.value);
  targetBlockId.value = index >= 0 ? blocks.value[index + 1]?.id || null : null;
}
async function handleSourceChange() { chooseTarget(); await loadPage(); }

async function loadPage() {
  if (!cycleId.value || !sourceBlockId.value) { summary.value = null; return; }
  loading.value = true;
  try {
    const [summaryResult, historyResult] = await Promise.all([
      getWeeklyReviewSummary(cycleId.value, sourceBlockId.value),
      listWeeklyReviews(cycleId.value),
    ]);
    summary.value = summaryResult;
    history.value = historyResult.items.filter((item) => item.source_block_id === sourceBlockId.value);
    const latest = history.value[0];
    detail.value = latest ? await getWeeklyReview(latest.id) : null;
    selectedReviewId.value = latest?.id || null;
    trackUsageEvent("weekly_review_summary_viewed", { cycle_id: cycleId.value, source_block_id: sourceBlockId.value });
    if (detail.value?.adjustment_draft) trackUsageEvent("adjustment_draft_viewed", { draft_id: detail.value.adjustment_draft.id });
  } finally { loading.value = false; }
}

async function generate() {
  if (!cycleId.value || !sourceBlockId.value || !targetBlockId.value || !summary.value) return;
  if (!summary.value.metrics.is_week_complete) await ElMessageBox.confirm("当前训练周尚未结束，确定提前生成复盘吗？", "提前复盘", { type: "warning" });
  generating.value = true;
  const eventBase = { cycle_id: cycleId.value, source_block_id: sourceBlockId.value, target_block_id: targetBlockId.value };
  trackUsageEvent(detail.value ? "weekly_review_regenerated" : "weekly_review_generate_started", eventBase);
  try {
    detail.value = await generateWeeklyReview({ cycle_id: cycleId.value, source_block_id: sourceBlockId.value, target_block_id: targetBlockId.value, force_regenerate: Boolean(detail.value) });
    selectedReviewId.value = detail.value.report.id;
    trackUsageEvent("weekly_review_generate_succeeded", { ...eventBase, review_id: detail.value.report.id });
    await loadPage();
    ElMessage.success("周复盘与调整草稿已生成");
  } catch (error) {
    trackUsageEvent("weekly_review_generate_failed", { ...eventBase, error_type: "request_failed" });
    throw error;
  } finally { generating.value = false; }
}

async function loadHistoryDetail() { if (selectedReviewId.value) detail.value = await getWeeklyReview(selectedReviewId.value); }
async function toggleItem(item: AdjustmentItem) {
  if (!draft.value) return;
  detail.value = await updateAdjustmentItem(draft.value.id, item.id, { is_selected: item.is_selected });
  trackUsageEvent("adjustment_item_selected", { draft_id: draft.value.id, item_id: item.id, selected: item.is_selected });
}
async function setAll(selected: boolean) {
  if (!draft.value) return;
  for (const item of draft.value.items.filter((candidate) => !candidate.is_applied && candidate.is_selected !== selected)) {
    detail.value = await updateAdjustmentItem(draft.value.id, item.id, { is_selected: selected });
  }
}
function openEdit(item: AdjustmentItem) {
  editingItemId.value = item.id;
  editForm.suggested_content = item.suggested_content;
  editForm.suggested_distance_km = Number(item.suggested_distance_km || 0);
  editForm.suggested_main_type = (item.suggested_main_type || "easy") as WorkoutMainTypeNormalized;
  editForm.suggested_target_pace_text = item.suggested_target_pace_text || "";
  editVisible.value = true;
}
async function saveEdit() {
  if (!draft.value || !editingItemId.value) return;
  savingItem.value = true;
  try {
    detail.value = await updateAdjustmentItem(draft.value.id, editingItemId.value, { ...editForm });
    trackUsageEvent("adjustment_item_edited", { draft_id: draft.value.id, item_id: editingItemId.value });
    editVisible.value = false;
    ElMessage.success("建议已保存并通过校验");
  } finally { savingItem.value = false; }
}
async function applyDraft() {
  if (!draft.value || !selectedItemIds.value.length) return;
  await ElMessageBox.confirm(`将修改下一周 ${selectedItemIds.value.length} 项训练，确认应用吗？`, "应用训练调整", { type: "warning", confirmButtonText: "确认应用" });
  applying.value = true;
  try {
    await applyAdjustmentDraft(draft.value.id, selectedItemIds.value);
    trackUsageEvent("adjustment_draft_applied", { draft_id: draft.value.id, selected_count: selectedItemIds.value.length });
    detail.value = await getWeeklyReview(detail.value!.report.id);
    ElMessage.success("已应用所选调整，今日训练和日历将显示新计划");
  } finally { applying.value = false; }
}
async function rejectDraft() {
  if (!draft.value) return;
  await ElMessageBox.confirm("确认保留下一周原计划并拒绝这份调整草稿吗？", "保留原计划", { type: "warning" });
  detail.value = await rejectAdjustmentDraft(draft.value.id);
  trackUsageEvent("adjustment_draft_rejected", { draft_id: draft.value.id });
}

onMounted(async () => {
  trackUsageEvent("weekly_review_viewed");
  cycles.value = await listTrainingCycles();
  if (!cycleId.value) cycleId.value = cycles.value[0]?.id || null;
  if (cycleId.value) {
    blocks.value = await listTrainingBlocks(cycleId.value);
    if (!sourceBlockId.value) sourceBlockId.value = blocks.value[blocks.value.length - 1]?.id || null;
    chooseTarget();
    await loadPage();
  }
});
</script>

<style scoped>
.weekly-review-page { gap: 18px; }
.review-toolbar .el-select { width: 210px; }
.section-heading, .adjustment-head, .status-title, .draft-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.section-heading h2, .status-title h2 { margin: 0; font-size: 17px; }
.section-heading span { color: var(--muted); font-size: 12px; }
.review-metrics { display: grid; grid-template-columns: repeat(7, minmax(110px, 1fr)); gap: 10px; margin-top: 12px; }
.review-section { padding: 18px; }
.daily-review-grid, .adjustment-list { display: grid; gap: 10px; margin-top: 14px; }
.daily-review-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.daily-review-card, .adjustment-card, .review-copy-grid article, .strategy-card { padding: 14px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
.daily-review-card > div, .adjustment-head > div { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.daily-review-card p { margin: 10px 0; line-height: 1.55; }
.daily-review-card > span, .plan-compare span, .plan-compare small { color: var(--muted); font-size: 12px; }
.completion-notes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
.completion-notes p { margin: 0; padding: 11px; background: var(--surface-muted); border-radius: var(--card-radius); }
.status-section ul, .review-copy-grid ul { margin-bottom: 0; padding-left: 20px; line-height: 1.8; }
.safety-note { color: var(--muted); font-size: 12px; }
.review-summary { font-size: 15px; line-height: 1.8; }
.review-copy-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.review-copy-grid h3, .strategy-card h3 { margin: 0; font-size: 15px; }
.strategy-card { margin-top: 12px; }
.strategy-card p { margin-bottom: 0; line-height: 1.7; }
.ai-review-section :deep(.el-alert) { margin-top: 10px; }
.adjustment-card.selected { border-color: var(--primary); background: #f8fbff; }
.plan-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }
.plan-compare > div { padding: 12px; border-radius: var(--card-radius); background: #f7f8fa; }
.plan-compare .suggested { background: #eef8f4; }
.plan-compare p { min-height: 48px; margin: 8px 0; line-height: 1.6; }
.adjustment-reason { color: #475467; line-height: 1.6; }
.selection-actions, .draft-actions { display: flex; }
.draft-actions { justify-content: flex-end; margin-top: 16px; }
.mobile-apply-bar { display: none; }
.edit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 900px) { .review-metrics { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 768px) {
  .review-toolbar .el-select { width: 100%; }
  .review-metrics { grid-template-columns: repeat(2, 1fr); }
  .daily-review-grid, .review-copy-grid, .completion-notes, .plan-compare, .edit-grid { grid-template-columns: 1fr; }
  .section-heading { align-items: flex-start; flex-direction: column; }
  .selection-actions { width: 100%; justify-content: space-between; }
  .plan-compare p { min-height: 0; }
  .draft-actions { display: none; }
  .mobile-apply-bar { position: sticky; bottom: 70px; z-index: 20; display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: 0 -4px 16px rgba(23,32,51,.14); }
}
</style>
