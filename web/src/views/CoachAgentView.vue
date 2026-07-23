<template>
  <div class="page-stack coach-page">
    <PageHeader
      title="AI 教练"
      subtitle="基于训练事实、Runner State 和科学规则生成解释与建议"
    />

    <section class="coach-intro" aria-label="AI 教练使用边界">
      <div class="boundary-tags">
        <span>只读建议</span>
        <span>规则约束</span>
        <span>不会自动改课表</span>
      </div>
      <p>建议仅供训练决策参考，不用于医疗诊断，也不会自动修改训练计划。</p>
    </section>

    <section class="intent-section" aria-labelledby="coach-intent-title">
      <div class="section-title">
        <span>快捷入口</span>
        <h2 id="coach-intent-title">你想了解什么？</h2>
      </div>
      <div class="intent-grid">
        <button
          v-for="item in quickIntents"
          :key="item.intent"
          type="button"
          class="intent-card"
          :class="{ active: selectedIntent === item.intent }"
          :aria-pressed="selectedIntent === item.intent"
          @click="selectIntent(item.intent)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <strong>{{ item.title }}</strong>
          <span>{{ item.description }}</span>
        </button>
      </div>
    </section>

    <section class="input-panel" aria-labelledby="coach-input-title">
      <div class="input-heading">
        <div>
          <span>当前能力：{{ coachIntentDisplay[selectedIntent] }}</span>
          <h2 id="coach-input-title">向教练提问</h2>
        </div>
        <el-button v-if="turns.length" text @click="clearConversation">清空会话</el-button>
      </div>
      <label for="coach-message">训练问题</label>
      <el-input
        id="coach-message"
        v-model="message"
        type="textarea"
        :rows="4"
        :maxlength="MAX_MESSAGE_LENGTH"
        show-word-limit
        resize="vertical"
        :disabled="loading"
        :placeholder="inputPlaceholder"
        @keydown.ctrl.enter.prevent="submitQuery"
      />
      <div class="input-actions">
        <span>Ctrl + Enter 发送；会话仅保存在当前页面内存中。</span>
        <el-button
          class="send-button"
          type="primary"
          :loading="loading"
          :disabled="!canSubmit"
          @click="submitQuery"
        >
          发送问题
        </el-button>
      </div>
      <p v-if="errorMessage" class="request-error" role="alert">{{ errorMessage }}</p>
      <p v-if="conversationTrimmed" class="trim-notice" role="status">
        为保护隐私并控制上下文长度，较早的公开问答已从本次上下文中裁剪。
      </p>
      <p v-if="loading" class="loading-status" aria-live="polite">正在读取训练事实并生成安全建议……</p>
    </section>

    <section v-if="turns.length" class="conversation" aria-label="本次页面会话">
      <article v-for="turn in turns" :key="turn.id" class="conversation-turn">
        <div class="user-question">
          <span>你的问题</span>
          <p>{{ turn.question }}</p>
        </div>

        <CoachTodayRecommendationCard
          v-if="turn.response.today_recommendation"
          :recommendation="turn.response.today_recommendation"
          :risk-level="turn.response.risk_level"
        />
        <CoachSafetyNotices
          :warnings="turn.response.warnings"
          :limitations="turn.response.limitations"
          :risk-level="turn.response.risk_level"
        />
        <CoachAnswerCard
          :status="turn.response.status"
          :answer="turn.response.answer"
          :summary="turn.response.summary"
          :generated-at="turn.response.generated_at"
          :provider-status="turn.response.provider_status"
        />
        <CoachToolSummary :tools="turn.response.tool_calls" />
      </article>
    </section>

    <section v-else class="empty-state">
      <el-icon><ChatDotRound /></el-icon>
      <h2>从一个训练问题开始</h2>
      <p>确定性规则结论会优先展示，AI 只负责解释已有事实。</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { ChatDotRound, DataAnalysis, Timer } from "@element-plus/icons-vue";
import { getCoachAgentErrorMessage, queryCoach } from "@/api/coachAgent";
import CoachAnswerCard from "@/components/coach/CoachAnswerCard.vue";
import CoachSafetyNotices from "@/components/coach/CoachSafetyNotices.vue";
import CoachTodayRecommendationCard from "@/components/coach/CoachTodayRecommendationCard.vue";
import CoachToolSummary from "@/components/coach/CoachToolSummary.vue";
import PageHeader from "@/components/PageHeader.vue";
import type { CoachAgentIntent } from "@/types/coachAgent";
import {
  appendCoachTurn,
  buildCoachConversationContext,
  type CoachConversationTurn,
} from "@/utils/coachAgentConversation";
import { coachIntentDisplay } from "@/utils/coachAgentDisplay";

const MAX_MESSAGE_LENGTH = 4000;
const DEFAULT_QUESTIONS: Record<CoachAgentIntent, string> = {
  TODAY_RECOMMENDATION: "根据我今天的计划、近期训练和当前状态，我今天应该怎么训练？请说明依据和限制。",
  EXPLAIN_RUNNER_STATE: "请解释我当前的 Runner State、主要依据，以及哪些结论可能因为数据不足而不可靠。",
  GENERAL_TRAINING_QUESTION: "",
};

const quickIntents = [
  {
    intent: "TODAY_RECOMMENDATION" as const,
    title: "今日训练建议",
    description: "结合今日计划、近期训练和规则评估。",
    icon: Timer,
  },
  {
    intent: "EXPLAIN_RUNNER_STATE" as const,
    title: "解释当前状态",
    description: "了解 Runner State 的依据与数据限制。",
    icon: DataAnalysis,
  },
  {
    intent: "GENERAL_TRAINING_QUESTION" as const,
    title: "一般训练问题",
    description: "询问公开训练规则，不生成或修改课表。",
    icon: ChatDotRound,
  },
];

const selectedIntent = ref<CoachAgentIntent>("TODAY_RECOMMENDATION");
const message = ref(DEFAULT_QUESTIONS.TODAY_RECOMMENDATION);
const turns = ref<CoachConversationTurn[]>([]);
const loading = ref(false);
const errorMessage = ref("");
const conversationTrimmed = ref(false);
let active = true;
let controller: AbortController | null = null;

const inputPlaceholder = computed(() => selectedIntent.value === "GENERAL_TRAINING_QUESTION"
  ? "请输入你的训练问题"
  : "可以修改示例问题后发送");
const canSubmit = computed(() => {
  const length = message.value.trim().length;
  return !loading.value && length > 0 && length <= MAX_MESSAGE_LENGTH;
});

function selectIntent(intent: CoachAgentIntent) {
  selectedIntent.value = intent;
  message.value = DEFAULT_QUESTIONS[intent];
  errorMessage.value = "";
}

function clearConversation() {
  turns.value = [];
  conversationTrimmed.value = false;
  errorMessage.value = "";
}

async function submitQuery() {
  if (!canSubmit.value) return;
  const question = message.value.trim();
  const context = buildCoachConversationContext(turns.value);
  conversationTrimmed.value ||= context.trimmed;
  loading.value = true;
  errorMessage.value = "";
  controller = new AbortController();
  try {
    const response = await queryCoach({
      message: question,
      intent: selectedIntent.value,
      conversation_context: context.messages,
    }, controller.signal);
    if (!active) return;
    const appended = appendCoachTurn(turns.value, {
      id: response.request_id,
      question,
      response,
    });
    turns.value = appended.turns;
    conversationTrimmed.value ||= appended.trimmed;
    message.value = "";
  } catch (error) {
    if (!active) return;
    errorMessage.value = getCoachAgentErrorMessage(error);
  } finally {
    if (active) loading.value = false;
    controller = null;
  }
}

onBeforeUnmount(() => {
  active = false;
  controller?.abort();
});
</script>

<style scoped>
.coach-page { max-width: 1080px; margin: 0 auto; gap: 16px; padding-bottom: 24px; }
.coach-intro, .intent-section, .input-panel, .empty-state { min-width: 0; padding: 18px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; box-shadow: var(--card-shadow); }
.boundary-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.boundary-tags span { padding: 6px 9px; border-radius: 999px; color: #1f4e79; background: var(--blue-soft); font-size: 12px; font-weight: 700; }
.coach-intro p { margin: 12px 0 0; color: #475467; line-height: 1.65; }
.section-title span, .input-heading span { color: #1f4e79; font-size: 12px; font-weight: 700; }
.section-title h2, .input-heading h2, .empty-state h2 { margin: 4px 0 0; color: #172033; font-size: 20px; }
.intent-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.intent-card { display: grid; grid-template-columns: auto 1fr; gap: 5px 10px; min-width: 0; padding: 15px; text-align: left; border: 1px solid #d8e2ec; border-radius: 8px; color: #26354a; background: #fbfcfd; cursor: pointer; }
.intent-card:hover, .intent-card.active { border-color: #5c8fbd; background: #f2f7fc; }
.intent-card:focus-visible { outline: 3px solid rgba(25, 118, 210, .3); outline-offset: 2px; }
.intent-card .el-icon { grid-row: 1 / 3; color: #1976d2; font-size: 24px; }
.intent-card strong, .intent-card span { min-width: 0; overflow-wrap: anywhere; }
.intent-card span { color: #667085; font-size: 12px; line-height: 1.5; }
.input-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.input-panel label { display: inline-block; margin-bottom: 7px; color: #344054; font-size: 13px; font-weight: 700; }
.input-actions { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 12px; }
.input-actions span { color: #667085; font-size: 12px; }
.request-error, .trim-notice, .loading-status { margin: 12px 0 0; padding: 10px 12px; border-radius: 6px; line-height: 1.55; }
.request-error { color: #9f352e; background: #fff2f0; }
.trim-notice { color: #7a5713; background: #fff8e8; }
.loading-status { color: #1f4e79; background: #f1f7fc; }
.conversation { display: grid; gap: 18px; }
.conversation-turn { display: grid; gap: 12px; min-width: 0; padding-top: 18px; border-top: 1px solid #dfe5ec; }
.user-question { max-width: 84%; margin-left: auto; padding: 12px 15px; border-radius: 12px 12px 2px 12px; color: #fff; background: #315f88; }
.user-question span { font-size: 11px; opacity: .8; }
.user-question p { margin: 4px 0 0; overflow-wrap: anywhere; white-space: pre-wrap; line-height: 1.65; }
.empty-state { display: grid; justify-items: center; padding: 36px 18px; text-align: center; }
.empty-state .el-icon { color: #5b7fa3; font-size: 38px; }
.empty-state p { margin: 9px 0 0; color: #667085; }
@media (max-width: 768px) {
  .coach-page { padding-bottom: 88px; }
  .intent-grid { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .coach-intro, .intent-section, .input-panel, .empty-state { padding: 14px; }
  .input-heading, .input-actions { align-items: stretch; flex-direction: column; }
  .send-button { width: 100%; min-height: 44px; }
  .user-question { max-width: 96%; }
}
</style>
