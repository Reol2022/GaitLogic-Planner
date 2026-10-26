<template>
  <div class="coach-chat-page">
    <header class="coach-chat-header">
      <div>
        <p class="eyebrow">GaitLogic AI Coach</p>
        <h1>和你的训练教练持续交流</h1>
        <p>建议基于当前训练事实与训练知识生成，不会直接修改正式训练计划。</p>
      </div>
      <el-button class="mobile-history" plain @click="drawerOpen = true">历史会话</el-button>
    </header>

    <div class="coach-chat-layout">
      <aside class="conversation-panel desktop-conversations">
        <CoachConversationList
          :items="conversations"
          :active-id="activeConversationId ?? undefined"
          :loading="conversationsLoading"
          @create="createConversation"
          @select="selectConversation"
          @rename="renameConversation"
          @archive="archiveConversation"
          @delete="removeConversation"
        />
      </aside>

      <main class="chat-panel">
        <div v-if="!activeConversationId" class="empty-chat">
          <h2>从一个问题开始</h2>
          <p>新对话会自动保存，关闭页面后仍可继续。</p>
          <div class="quick-prompts">
            <el-button v-for="prompt in quickPrompts" :key="prompt" @click="startWithPrompt(prompt)">
              {{ prompt }}
            </el-button>
          </div>
        </div>

        <template v-else>
          <div ref="messageListRef" class="message-list" aria-live="polite">
            <div v-if="messagesLoading" class="message-loading"><el-skeleton :rows="5" animated /></div>
            <template v-else>
              <article v-for="item in messages" :key="item.id" class="chat-message" :class="item.role">
                <span class="message-role">{{ item.role === "user" ? "你" : "AI 教练" }}</span>
                <div class="message-bubble">
                  <p v-if="item.content" class="message-content">{{ item.content }}</p>
                  <div v-else-if="item.status === 'pending'" class="execution-card">
                    <span class="execution-current">{{ progressLabel(item.progress?.stage) }}</span>
                    <details v-if="item.progress?.summary?.length" class="execution-details">
                      <summary>查看已获取信息</summary>
                      <p v-for="summary in item.progress.summary" :key="summary.code">
                        {{ summary.message }}<template v-if="summary.count !== null && summary.count !== undefined">：{{ summary.count }} 条</template>
                      </p>
                    </details>
                  </div>
                  <p v-else class="message-state">本轮回复未能完成，可重试。</p>
                  <div v-if="item.role === 'assistant' && item.warnings.length" class="notice-list warning">
                    <p v-for="notice in item.warnings" :key="notice.code">{{ notice.message }}</p>
                  </div>
                  <div v-if="item.role === 'assistant' && item.limitations.length" class="notice-list limitation">
                    <p v-for="notice in item.limitations" :key="notice.code">{{ notice.message }}</p>
                  </div>
                  <details v-if="item.role === 'assistant' && item.evidence_refs.length" class="evidence-details">
                    <summary>训练知识依据（{{ item.evidence_refs.length }}）</summary>
                    <p v-for="reference in item.evidence_refs" :key="reference.document_id + reference.section">
                      <strong>{{ reference.title }}</strong>：{{ reference.excerpt }}
                    </p>
                  </details>
                </div>
              </article>
            </template>
          </div>

          <div v-if="submitError" class="submit-error">
            <span>{{ submitError }}</span>
            <el-button v-if="retryPayload" size="small" @click="retryLastMessage">重试</el-button>
          </div>
          <form class="composer" @submit.prevent="sendMessage">
            <el-input
              v-model="draft"
              type="textarea"
              :rows="3"
              maxlength="4000"
              show-word-limit
              placeholder="例如：昨天间歇练得怎么样？那周四还能练节奏吗？"
              :disabled="sending"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <div class="composer-actions">
              <span>Enter 发送，Shift + Enter 换行</span>
              <el-button type="primary" native-type="submit" :loading="sending" :disabled="!draft.trim()">
                发送
              </el-button>
            </div>
          </form>
        </template>
      </main>
    </div>

    <el-drawer v-model="drawerOpen" title="历史会话" direction="ltr" size="86%" class="history-drawer">
      <CoachConversationList
        :items="conversations"
        :active-id="activeConversationId ?? undefined"
        :loading="conversationsLoading"
        @create="createConversation"
        @select="selectConversation"
        @rename="renameConversation"
        @archive="archiveConversation"
        @delete="removeConversation"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import CoachConversationList from "@/components/coach/CoachConversationList.vue";
import {
  createCoachConversation,
  deleteCoachConversation,
  getCoachAgentErrorMessage,
  getCoachConversationMessages,
  getCoachConversationTurnStatus,
  listCoachConversations,
  sendCoachConversationMessage,
  updateCoachConversation,
} from "@/api/coachAgent";
import type { CoachConversation, CoachStoredMessage, CoachTurnProgress, CoachTurnStage } from "@/types/coachAgent";

const quickPrompts = ["今天怎么练？", "看看最近状态", "帮我复盘本周", "讨论训练计划"];
const conversations = ref<CoachConversation[]>([]);
const messages = ref<CoachStoredMessage[]>([]);
const activeConversationId = ref<string | null>(null);
const conversationsLoading = ref(false);
const messagesLoading = ref(false);
const sending = ref(false);
const drawerOpen = ref(false);
const draft = ref("");
const submitError = ref("");
const retryPayload = ref<{ message: string; turnId: string } | null>(null);
const messageListRef = ref<HTMLElement | null>(null);
let progressPollToken = 0;

const progressLabels: Record<CoachTurnStage, string> = {
  QUEUED: "正在排队准备本轮分析",
  CONTEXT_LOADING: "正在准备对话上下文",
  FACTS_LOADING: "正在读取训练数据",
  FACTS_READY: "已获取训练事实，正在组织分析",
  GENERATING: "正在生成训练分析",
  VALIDATING: "正在核对回答",
  COMPLETED: "分析已完成",
  FAILED: "本轮分析未能完成",
};

function progressLabel(stage?: CoachTurnStage): string {
  return stage ? progressLabels[stage] : progressLabels.QUEUED;
}

function turnId(): string {
  return crypto.randomUUID ? crypto.randomUUID().replace(/-/g, "") : `${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

async function refreshConversations(): Promise<void> {
  conversationsLoading.value = true;
  try {
    conversations.value = (await listCoachConversations()).items;
  } finally {
    conversationsLoading.value = false;
  }
}

async function loadMessages(id: string): Promise<void> {
  messagesLoading.value = true;
  submitError.value = "";
  retryPayload.value = null;
  try {
    messages.value = (await getCoachConversationMessages(id)).items;
    await scrollToBottom();
  } catch (error) {
    ElMessage.error(getCoachAgentErrorMessage(error));
  } finally {
    messagesLoading.value = false;
  }
}

async function selectConversation(id: string): Promise<void> {
  stopProgressPolling();
  activeConversationId.value = id;
  drawerOpen.value = false;
  await loadMessages(id);
}

async function createConversation(): Promise<void> {
  try {
    const conversation = await createCoachConversation();
    await refreshConversations();
    await selectConversation(conversation.id);
  } catch (error) {
    ElMessage.error(getCoachAgentErrorMessage(error));
  }
}

async function startWithPrompt(prompt: string): Promise<void> {
  if (!activeConversationId.value) await createConversation();
  draft.value = prompt;
  await sendMessage();
}

async function sendMessage(): Promise<void> {
  const message = draft.value.trim();
  if (!message || !activeConversationId.value || sending.value) return;
  const payload = { message, turnId: turnId() };
  draft.value = "";
  await submit(payload);
}

async function retryLastMessage(): Promise<void> {
  if (retryPayload.value && !sending.value) await submit(retryPayload.value, true);
}

function stopProgressPolling(): void {
  progressPollToken += 1;
}

function queuedProgress(): CoachTurnProgress {
  return { stage: "QUEUED", sequence: 0, summary: [], terminal: false };
}

function showOptimisticTurn(payload: { message: string; turnId: string }, retry: boolean): string {
  const localAssistantId = `pending-${payload.turnId}`;
  if (retry) {
    const failedIndex = [...messages.value]
      .map((item) => item.role === "assistant" && item.status === "failed")
      .lastIndexOf(true);
    if (failedIndex >= 0) {
      messages.value[failedIndex] = {
        ...messages.value[failedIndex],
        content: null,
        status: "pending",
        progress: queuedProgress(),
      };
      return messages.value[failedIndex].id;
    }
  }
  const timestamp = new Date().toISOString();
  const nextSequence = Math.max(0, ...messages.value.map((item) => item.sequence_no)) + 1;
  messages.value.push(
    {
      id: `local-user-${payload.turnId}`,
      role: "user",
      content: payload.message,
      status: "completed",
      sequence_no: nextSequence,
      evidence_refs: [],
      created_at: timestamp,
      warnings: [],
      limitations: [],
      tool_calls: [],
    },
    {
      id: localAssistantId,
      role: "assistant",
      content: null,
      status: "pending",
      sequence_no: nextSequence + 1,
      evidence_refs: [],
      created_at: timestamp,
      warnings: [],
      limitations: [],
      tool_calls: [],
      progress: queuedProgress(),
    },
  );
  void scrollToBottom();
  return localAssistantId;
}

function applyProgress(localAssistantId: string, progress: CoachTurnProgress): void {
  const index = messages.value.findIndex((item) => item.id === localAssistantId);
  if (index >= 0) messages.value[index] = { ...messages.value[index], progress };
}

async function pollTurnProgress(
  conversationId: string,
  clientTurnId: string,
  localAssistantId: string,
): Promise<void> {
  const token = ++progressPollToken;
  let delayMs = 700;
  while (token === progressPollToken && activeConversationId.value === conversationId) {
    try {
      const status = await getCoachConversationTurnStatus(conversationId, clientTurnId);
      if (token !== progressPollToken || activeConversationId.value !== conversationId) return;
      applyProgress(localAssistantId, status.progress);
      if (status.progress.terminal || status.message_status !== "pending") return;
    } catch {
      // The first read may race the POST's durable turn reservation. Retrying
      // retains the queued state instead of presenting a false failure.
    }
    await new Promise<void>((resolve) => window.setTimeout(resolve, delayMs));
    delayMs = Math.min(2_000, Math.round(delayMs * 1.35));
  }
}

async function submit(payload: { message: string; turnId: string }, retry = false): Promise<void> {
  if (!activeConversationId.value) return;
  const conversationId = activeConversationId.value;
  sending.value = true;
  submitError.value = "";
  retryPayload.value = null;
  const localAssistantId = showOptimisticTurn(payload, retry);
  const poll = pollTurnProgress(conversationId, payload.turnId, localAssistantId);
  try {
    const result = await sendCoachConversationMessage(conversationId, payload.message, payload.turnId);
    if (activeConversationId.value === conversationId) await loadMessages(conversationId);
    await refreshConversations();
    if (result.status !== "completed") {
      submitError.value = "本轮教练回复未完成，原问题已安全保存。";
      retryPayload.value = payload;
    }
  } catch (error) {
    submitError.value = getCoachAgentErrorMessage(error);
    retryPayload.value = payload;
  } finally {
    stopProgressPolling();
    await poll;
    sending.value = false;
  }
}

async function archiveConversation(id: string): Promise<void> {
  try {
    await updateCoachConversation(id, { status: "archived" });
    await refreshConversations();
    if (activeConversationId.value === id) activeConversationId.value = null;
    drawerOpen.value = false;
  } catch (error) {
    ElMessage.error(getCoachAgentErrorMessage(error));
  }
}

async function renameConversation(id: string, currentTitle: string): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt("输入新的对话名称", "重命名对话", {
      inputValue: currentTitle,
      inputPlaceholder: "例如：10 月训练分析",
      inputValidator: (input) => {
        const normalized = input.trim();
        if (!normalized) return "对话名称不能为空";
        if (normalized.length > 160) return "对话名称不能超过 160 个字符";
        return true;
      },
      confirmButtonText: "保存",
      cancelButtonText: "取消",
      closeOnClickModal: false,
    });
    const title = value.trim();
    if (title === currentTitle.trim()) return;
    await updateCoachConversation(id, { title });
    await refreshConversations();
    ElMessage.success("对话名称已更新");
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(getCoachAgentErrorMessage(error));
  }
}

async function removeConversation(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm("删除后无法恢复该会话及其中消息，是否继续？", "删除会话", { type: "warning" });
    await deleteCoachConversation(id);
    if (activeConversationId.value === id) {
      stopProgressPolling();
      activeConversationId.value = null;
      messages.value = [];
    }
    await refreshConversations();
    drawerOpen.value = false;
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(getCoachAgentErrorMessage(error));
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick();
  if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight;
}

onMounted(async () => {
  await refreshConversations();
  if (conversations.value[0]) await selectConversation(conversations.value[0].id);
});

onBeforeUnmount(stopProgressPolling);
</script>

<style scoped>
.coach-chat-page { max-width: 1260px; margin: 0 auto; padding: 22px; }
.coach-chat-header { display: flex; justify-content: space-between; gap: 18px; align-items: start; margin-bottom: 18px; }
.coach-chat-header h1 { margin: 4px 0 8px; font-size: 26px; }.coach-chat-header p { margin: 0; color: var(--el-text-color-secondary); }
.eyebrow { color: var(--el-color-primary) !important; font-weight: 700; font-size: 13px; }.mobile-history { display: none; }
.coach-chat-layout { display: grid; grid-template-columns: 270px minmax(0, 1fr); min-height: 650px; border: 1px solid var(--el-border-color-light); border-radius: 14px; overflow: hidden; background: var(--el-bg-color); }
.conversation-panel { border-right: 1px solid var(--el-border-color-light); padding: 16px 12px; background: linear-gradient(180deg, var(--el-fill-color-lighter), var(--el-bg-color)); }
.chat-panel { display: flex; min-width: 0; min-height: 0; flex-direction: column; }.empty-chat { display: grid; place-content: center; min-height: 580px; text-align: center; padding: 28px; }.empty-chat h2 { margin-bottom: 8px; }.empty-chat p { color: var(--el-text-color-secondary); }.quick-prompts { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 18px; }
.message-list { flex: 1; overflow-y: auto; padding: 24px; display: grid; align-content: start; gap: 18px; }.message-loading { padding: 20px; }.chat-message { display: grid; gap: 5px; max-width: min(760px, 90%); }.chat-message.user { justify-self: end; }.message-role { font-size: 12px; color: var(--el-text-color-secondary); }.user .message-role { text-align: right; }.message-bubble { border-radius: 12px; padding: 12px 14px; background: var(--el-fill-color-light); }.user .message-bubble { background: var(--el-color-primary-light-8); }.message-content { margin: 0; white-space: pre-wrap; line-height: 1.65; }.message-state { margin: 0; color: var(--el-text-color-secondary); }.execution-card { display: grid; gap: 8px; min-width: 220px; }.execution-current { display: flex; align-items: center; gap: 8px; color: var(--el-text-color-regular); font-size: 14px; }.execution-current::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--el-color-primary); animation: coach-progress-pulse 1.1s ease-in-out infinite; }.execution-details { color: var(--el-text-color-secondary); font-size: 13px; }.execution-details summary { cursor: pointer; }.execution-details p { margin: 5px 0 0; }.notice-list { margin-top: 10px; padding: 8px 10px; border-radius: 6px; font-size: 13px; }.notice-list p { margin: 0 0 4px; }.notice-list p:last-child { margin-bottom: 0; }.warning { background: var(--el-color-warning-light-9); }.limitation { background: var(--el-fill-color); }.evidence-details { margin-top: 10px; font-size: 13px; color: var(--el-text-color-secondary); }.evidence-details p { margin: 6px 0 0; }.submit-error { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin: 0 18px 8px; padding: 8px 10px; color: var(--el-color-danger); background: var(--el-color-danger-light-9); border-radius: 6px; }.composer { border-top: 1px solid var(--el-border-color-light); padding: 14px; }.composer-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px; } @keyframes coach-progress-pulse { 0%, 100% { opacity: .35; transform: scale(.8); } 50% { opacity: 1; transform: scale(1); } }
@media (max-width: 760px) { .coach-chat-page { padding: 14px; }.coach-chat-header h1 { font-size: 22px; }.desktop-conversations { display: none; }.mobile-history { display: inline-flex; }.coach-chat-layout { display: block; min-height: 590px; }.message-list { padding: 16px; }.chat-message { max-width: 96%; }.composer-actions span { display: none; } }
</style>
