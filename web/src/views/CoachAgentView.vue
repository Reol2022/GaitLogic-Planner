<template>
  <div class="coach-chat-page" :class="{'is-short-viewport':shortViewport}" :style="viewportHeight ? {'--coach-viewport-height':`${viewportHeight}px`} : undefined">
    <header class="coach-chat-header">
      <div class="gilo-heading">
        <GiloAvatar />
        <div><p class="eyebrow">Gilo · Your AI Running Coach</p>
        <h1>和 Gilo 聊训练</h1>
        <p class="gilo-tagline">GaitLogic 负责管理训练，Gilo 负责理解训练。</p></div>
      </div>
      <el-button class="mobile-history" plain @click="drawerOpen = true">历史会话</el-button>
      <el-button v-if="entryPrompt && shortViewport" :disabled="sending" :loading="preparingEntry" @click="prepareContextConversation">带入问题</el-button>
    </header>

    <section v-if="entryPrompt && !shortViewport" class="context-entry" aria-label="来自训练页面的问题">
      <div><strong>带着当前训练问题开始</strong><p>{{ entryPrompt }}</p><small>仅准备问题；发送后会重新查询你有权访问的事实，不自动修改计划。</small></div>
      <el-button :disabled="sending" :loading="preparingEntry" @click="prepareContextConversation">放入新对话</el-button>
    </section>
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
          <GiloWelcome :disabled="sending || startingPrompt" @select="startWithPrompt" />
        </div>

        <template v-else>
          <div ref="messageListRef" class="message-list" aria-live="polite">
            <div v-if="messagesLoading" class="message-loading"><el-skeleton :rows="5" animated /></div>
            <template v-else>
              <GiloWelcome v-if="!messages.length" :disabled="sending || startingPrompt" @select="startWithPrompt" />
              <TransitionGroup name="gilo-message" tag="div" class="message-turns">
              <article v-for="item in messages" :key="item.id" class="chat-message" :class="[item.role,{'is-pending':isWorking(item)}]">
                <span class="message-role"><GiloAvatar v-if="item.role==='assistant'" :active="isWorking(item)" />{{ item.role === "user" ? "你" : "Gilo · 洛教练" }}</span>
                <div class="message-bubble">
                  <p v-if="item.content" class="message-content">{{ item.content }}</p>
                  <div v-else-if="item.status === 'pending'" class="execution-card">
                    <div v-if="isWorking(item)" class="gilo-signal" aria-hidden="true"><i /><i /><i /><i /><i /></div>
                    <span class="execution-current">{{ progressLabel(item.progress?.stage) }}</span>
                    <details v-if="item.progress?.summary?.length" class="execution-details">
                      <summary>查看已获取信息</summary>
                      <p v-for="summary in item.progress.summary" :key="summary.code">
                        {{ summary.message }}<template v-if="summary.count !== null && summary.count !== undefined">：{{ summary.count }} 条</template>
                      </p>
                    </details>
                  </div>
                  <p v-else class="message-state">本轮回复未能完成，可重试。</p>
                  <details
                    v-if="item.role === 'assistant' && item.training_fact_context"
                    class="fact-details"
                  >
                    <summary>训练事实与统计口径</summary>
                    <p>
                      {{ item.training_fact_context.range_label }}：
                      {{ item.training_fact_context.range_start }} 至 {{ item.training_fact_context.range_end }}
                      （数据截至 {{ item.training_fact_context.as_of }}）
                    </p>
                    <p v-if="item.training_fact_context.sources.length">
                      来源：{{ item.training_fact_context.sources.join("、") }}
                    </p>
                    <p v-if="item.training_fact_context.gaps.length">
                      数据缺口：{{ item.training_fact_context.gaps.join("、") }}
                    </p>
                    <p v-for="issue in item.training_fact_context.issues" :key="issue.code">
                      {{ issue.message }}
                    </p>
                  </details>
                  <div v-if="item.role === 'assistant' && item.warnings.length" class="notice-list warning">
                    <p v-for="notice in item.warnings" :key="notice.code">{{ notice.message }}</p>
                  </div>
                  <details v-if="item.role === 'assistant' && item.limitations.length" class="notice-list limitation">
                    <summary>数据缺口与回答限制（{{ item.limitations.length }}）</summary>
                    <p v-for="notice in item.limitations" :key="notice.code">{{ notice.message }}</p>
                  </details>
                  <details v-if="item.role === 'assistant' && item.evidence_refs.length" class="evidence-details">
                    <summary>训练知识依据（{{ item.evidence_refs.length }}）</summary>
                    <p v-for="reference in item.evidence_refs" :key="reference.document_id + reference.section">
                      <strong>{{ reference.title }}</strong>：{{ reference.excerpt }}
                    </p>
                  </details>
                </div>
              </article>
              </TransitionGroup>
            </template>
          </div>

          <div v-if="submitError" class="submit-error">
            <span>{{ submitError }}</span>
            <el-button v-if="retryPayload" size="small" @click="retryLastMessage">重试</el-button>
          </div>
          <form class="composer" @submit.prevent="sendMessage">
            <span class="composer-label">问问 Gilo <span>· 你的下一步，从理解训练开始</span></span>
            <el-input
              v-model="draft"
              type="textarea"
              :rows="3"
              maxlength="4000"
              show-word-limit
              placeholder="洛教练，帮我看看最近的训练……"
              :disabled="sending"
              aria-label="发送给 AI 教练的消息"
              @keydown="onComposerKeydown"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRoute, useRouter } from "vue-router";
import { coachEntryPrompt } from "@/utils/coreExperience";
import { shouldSubmitCoachMessage } from "@/utils/coachKeyboard";
import CoachConversationList from "@/components/coach/CoachConversationList.vue";
import GiloAvatar from '@/components/coach/GiloAvatar.vue';
import GiloWelcome from '@/components/coach/GiloWelcome.vue';
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

function isWorking(message:CoachStoredMessage){return message.status==='pending' && !message.progress?.terminal && !['COMPLETED','FAILED'].includes(message.progress?.stage || '');}
const conversations = ref<CoachConversation[]>([]);
const messages = ref<CoachStoredMessage[]>([]);
const activeConversationId = ref<string | null>(null);
const conversationsLoading = ref(false);
const messagesLoading = ref(false);
const sending = ref(false);
const startingPrompt=ref(false);
const drawerOpen = ref(false);
const draft = ref("");
const route = useRoute();
const router = useRouter();
const preparingEntry = ref(false);
const consumedEntry=ref<string|null>(null);
const entryKey=computed(()=>JSON.stringify([route?.query.topic,route?.query.date]));
const entryPrompt = computed(() => consumedEntry.value===entryKey.value?null:coachEntryPrompt(route?.query.topic, route?.query.date));
watch(entryKey,()=>{consumedEntry.value=null;});
async function prepareContextConversation() {
  if (!entryPrompt.value || sending.value || preparingEntry.value) return;
  const prompt=entryPrompt.value,key=entryKey.value;
  preparingEntry.value = true;
  try {
  if (draft.value.trim()) {
    try { await ElMessageBox.confirm('当前有未发送的问题，是否放弃并准备新问题？', '保留未发送内容', { confirmButtonText: '准备新问题', cancelButtonText: '继续编辑' }); }
    catch { return; }
  }
    if (await createConversation()) {
      draft.value = prompt;
      consumedEntry.value=key;
      const query={...route.query};delete query.topic;delete query.date;
      // Consume only the entry parameters; preserve unrelated navigation context.
      try{await router.replace({path:route.path || '/coach',query,hash:route.hash});}
      catch{ElMessage.warning('问题已放入对话，但地址未更新；刷新后可能再次显示入口提示。');}
    }
  } finally { preparingEntry.value = false; }
}
const submitError = ref("");
const retryPayload = ref<{ message: string; turnId: string } | null>(null);
const messageListRef = ref<HTMLElement | null>(null);
const viewportHeight = ref<number | null>(null);
const viewportWidth=ref(window.innerWidth);
const shortViewport=computed(()=>viewportWidth.value<=768 && viewportHeight.value!==null && viewportHeight.value<550);
function updateViewport(){viewportHeight.value=window.visualViewport?.height ?? window.innerHeight;viewportWidth.value=window.innerWidth;}
function onComposerKeydown(event:KeyboardEvent){
  if(shouldSubmitCoachMessage(event,window.innerWidth<=768)){event.preventDefault();void sendMessage();}
}
onMounted(()=>{updateViewport();window.visualViewport?.addEventListener('resize',updateViewport);window.addEventListener('resize',updateViewport);});
onBeforeUnmount(()=>{window.visualViewport?.removeEventListener('resize',updateViewport);window.removeEventListener('resize',updateViewport);});
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
  let loaded = false;
  try {
    messages.value = (await getCoachConversationMessages(id)).items;
    loaded = true;
  } catch (error) {
    ElMessage.error(getCoachAgentErrorMessage(error));
  } finally {
    messagesLoading.value = false;
  }
  // Wait until the loading skeleton has been replaced by the actual messages.
  // Scrolling before this point only scrolls the skeleton and leaves a restored
  // conversation at its oldest message.
  if (loaded && activeConversationId.value === id) await scrollToBottom();
}

async function selectConversation(id: string): Promise<void> {
  stopProgressPolling();
  activeConversationId.value = id;
  drawerOpen.value = false;
  await loadMessages(id);
}

async function createConversation(): Promise<boolean> {
  try {
    const conversation = await createCoachConversation();
    await refreshConversations();
    await selectConversation(conversation.id);
    return true;
  } catch (error) {
    ElMessage.error(getCoachAgentErrorMessage(error));
    return false;
  }
}

async function startWithPrompt(prompt: string): Promise<void> {
  if(startingPrompt.value || sending.value)return;
  startingPrompt.value=true;
  try{
    if (!activeConversationId.value && !(await createConversation())) return;
    draft.value = prompt;
    await sendMessage();
  }finally{startingPrompt.value=false;}
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
    stopProgressPolling();
    const pending=messages.value.find(item=>item.id===localAssistantId);
    if(pending){pending.status='failed';pending.progress={...pending.progress,stage:'FAILED',sequence:(pending.progress?.sequence || 0)+1,summary:pending.progress?.summary || [],terminal:true};}
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
.context-entry{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:16px 18px;border-radius:12px;border:1px solid var(--line);background:var(--el-color-primary-light-9);margin-bottom:14px}.context-entry p{margin:6px 0;line-height:1.6}.context-entry small{color:var(--muted)}.limitation summary{cursor:pointer}@media(max-width:640px){.context-entry{flex-direction:column;align-items:stretch}}
.coach-chat-page { max-width: 1260px; margin: 0 auto; padding: 22px; }
.coach-chat-header { display: flex; justify-content: space-between; gap: 18px; align-items: start; margin-bottom: 18px; }
.coach-chat-header h1 { margin: 4px 0 8px; font-size: 26px; }.coach-chat-header p { margin: 0; color: var(--el-text-color-secondary); }
.eyebrow { color: var(--el-color-primary) !important; font-weight: 700; font-size: 13px; }.mobile-history { display: none; }
.coach-chat-layout { display: grid; grid-template-columns: 270px minmax(0, 1fr); height: clamp(560px, calc(100dvh - 190px), 780px); border: 1px solid var(--el-border-color-light); border-radius: 14px; overflow: hidden; background: var(--el-bg-color); }
.conversation-panel { min-height: 0; overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; border-right: 1px solid var(--el-border-color-light); padding: 16px 12px; background: linear-gradient(180deg, var(--el-fill-color-lighter), var(--el-bg-color)); }
.chat-panel { display: flex; min-width: 0; min-height: 0; overflow: hidden; flex-direction: column; }.empty-chat { display: grid; flex: 1; place-content: center; text-align: center; padding: 28px; }.empty-chat h2 { margin-bottom: 8px; }.empty-chat p { color: var(--el-text-color-secondary); }.quick-prompts { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 18px; }
.message-list { min-height: 0; flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 24px; display: grid; align-content: start; gap: 18px; }.message-loading { padding: 20px; }.chat-message { display: grid; gap: 5px; max-width: min(760px, 90%); }.chat-message.user { justify-self: end; }.message-role { font-size: 12px; color: var(--el-text-color-secondary); }.user .message-role { text-align: right; }.message-bubble { border-radius: 12px; padding: 12px 14px; background: var(--el-fill-color-light); }.user .message-bubble { background: var(--el-color-primary-light-8); }.message-content { margin: 0; white-space: pre-wrap; line-height: 1.65; }.message-state { margin: 0; color: var(--el-text-color-secondary); }.execution-card { display: grid; gap: 8px; min-width: 220px; }.execution-current { display: flex; align-items: center; gap: 8px; color: var(--el-text-color-regular); font-size: 14px; }.execution-current::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--el-color-primary); animation: coach-progress-pulse 1.1s ease-in-out infinite; }.execution-details { color: var(--el-text-color-secondary); font-size: 13px; }.execution-details summary { cursor: pointer; }.execution-details p { margin: 5px 0 0; }.fact-details { margin-top: 10px; padding: 8px 10px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; color: var(--el-text-color-secondary); font-size: 12px; }.fact-details summary { color: var(--el-text-color-regular); cursor: pointer; font-weight: 600; }.fact-details p { margin: 6px 0 0; line-height: 1.5; }.notice-list { margin-top: 10px; padding: 8px 10px; border-radius: 6px; font-size: 13px; }.notice-list p { margin: 0 0 4px; }.notice-list p:last-child { margin-bottom: 0; }.warning { background: var(--el-color-warning-light-9); }.limitation { background: var(--el-fill-color); }.evidence-details { margin-top: 10px; font-size: 13px; color: var(--el-text-color-secondary); }.evidence-details p { margin: 6px 0 0; }.submit-error { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin: 0 18px 8px; padding: 8px 10px; color: var(--el-color-danger); background: var(--el-color-danger-light-9); border-radius: 6px; }.composer { flex: 0 0 auto; border-top: 1px solid var(--el-border-color-light); padding: 14px; }.composer-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px; } @keyframes coach-progress-pulse { 0%, 100% { opacity: .35; transform: scale(.8); } 50% { opacity: 1; transform: scale(1); } }
@media (max-width: 760px) { .coach-chat-page { padding: 14px; }.coach-chat-header h1 { font-size: 22px; }.desktop-conversations { display: none; }.mobile-history { display: inline-flex; }.coach-chat-layout { display: block; height: max(560px, calc(100dvh - 180px)); }.chat-panel { height: 100%; }.message-list { padding: 16px; }.chat-message { max-width: 96%; }.composer-actions span { display: none; } }
@media(max-width:768px){
  .coach-chat-page{height:calc(var(--coach-viewport-height,100dvh) - 64px - 62px - env(safe-area-inset-bottom,0px));min-height:0;padding:10px;display:flex;flex-direction:column;gap:10px;overflow:hidden}
  .coach-chat-header{margin:0;gap:10px;flex:0 0 auto;align-items:center}.coach-chat-header h1{font-size:18px;margin:3px 0}.coach-chat-header>div>p:last-child{display:none}.eyebrow{font-size:11px}.mobile-history{display:inline-flex;min-height:44px;flex-shrink:0}
  .desktop-conversations{display:none}.coach-chat-layout{display:flex;flex:1;min-height:0;height:auto;border-radius:12px}.chat-panel{height:100%;width:100%;min-height:0}.context-entry{margin:0;padding:10px;gap:8px;flex-direction:row;align-items:center;max-height:24dvh;overflow:auto;flex-shrink:0}.context-entry p{font-size:12px}.context-entry small{display:none}.context-entry>.el-button{min-height:44px;white-space:normal;flex-shrink:0;width:90px;height:auto;padding:9px}.context-entry strong{font-size:12px}
  .message-list{padding:12px;gap:14px;overflow-x:hidden}.message-content,.message-bubble{overflow-wrap:anywhere;word-break:break-word}.chat-message{max-width:100%;min-width:0}.execution-card{min-width:0}.empty-chat{min-height:0;overflow:auto;padding:18px}.empty-chat h2{font-size:19px}.quick-prompts{display:grid}.quick-prompts .el-button{min-height:44px;margin:0;white-space:normal;height:auto;padding:10px;line-height:1.5}.composer{padding:10px;min-width:0}.composer :deep(.el-textarea__inner){font-size:16px;max-height:120px}.composer-actions{justify-content:flex-end;margin-top:6px}.composer-actions>.el-button{min-height:44px;min-width:80px}.submit-error{flex-shrink:0;margin:0 10px 8px;overflow-wrap:anywhere}
}
@media(max-width:768px){
  .is-short-viewport .coach-chat-header .eyebrow{display:none}.is-short-viewport .coach-chat-header h1{font-size:15px;margin:0}.is-short-viewport .coach-chat-header>.el-button{margin:0;min-height:44px;flex-shrink:0}.is-short-viewport .coach-chat-header>div{min-width:0;flex:1}.is-short-viewport .composer{display:grid;grid-template-columns:minmax(0,1fr) 80px;align-items:end;gap:8px}.is-short-viewport .composer-actions{margin:0}.is-short-viewport .composer :deep(.el-textarea__inner){min-height:48px!important;max-height:64px}.is-short-viewport .composer-actions>.el-button{min-height:48px}
}
.coach-chat-page{--gilo-ink:#25384f;--gilo-accent:#258c9e;--gilo-line:#dfe9ef}
.gilo-heading{display:flex;align-items:center;gap:14px;min-width:0}.gilo-heading>.gilo-avatar{width:48px;height:48px}.coach-chat-header h1{color:var(--gilo-ink);font-size:24px;letter-spacing:-.6px}.eyebrow{color:#528297!important;letter-spacing:.06em;font-size:11px;font-weight:600}.coach-chat-header .gilo-tagline{font-size:12px;color:#7d8b9d}
.coach-chat-layout{border-color:var(--gilo-line);border-radius:20px;box-shadow:0 8px 36px #345b7f08;background:#fcfdff}.conversation-panel{background:linear-gradient(175deg,#f3f8fa,#f8f9fc);border-color:var(--gilo-line)}
.chat-panel{position:relative;isolation:isolate;background:radial-gradient(ellipse at 100% 0,#e9f2fa70,transparent 50%),#fcfdff}.empty-chat{display:flex;align-items:center;justify-content:center;overflow-y:auto;padding:20px}.message-turns{display:contents}.message-list{gap:24px;scrollbar-width:thin;scrollbar-color:#cfdae3 transparent}.message-role{display:flex;align-items:center;gap:8px;font-size:11px;font-weight:600;color:#72849a;margin-bottom:2px}.message-role .gilo-avatar{width:27px;height:27px}.user .message-role{justify-content:flex-end}.message-bubble{border:1px solid #e6edf2;border-radius:4px 16px 16px;background:#fff;box-shadow:0 3px 14px #345b7f05;color:#33465d}.user .message-bubble{background:linear-gradient(125deg,#edf6f8,#f0f1fc);border-color:#dfe7f1;border-radius:16px 4px 16px 16px}.message-content{font-size:14px;line-height:1.9}.is-pending .message-bubble{border-color:#cbdfe7;background:linear-gradient(125deg,#f5fbfc,#f8f7ff)}
.execution-current{color:#4f7187;font-size:13px}.execution-current::before{display:none}.gilo-signal{display:flex;align-items:center;gap:4px;height:22px}.gilo-signal i{width:4px;height:9px;border-radius:3px;background:linear-gradient(#7ca0d7,#5fbfbf);animation:gilo-signal 1.2s ease-in-out infinite}.gilo-signal i:nth-child(2){animation-delay:.12s}.gilo-signal i:nth-child(3){animation-delay:.24s}.gilo-signal i:nth-child(4){animation-delay:.36s}.gilo-signal i:nth-child(5){animation-delay:.48s}
.composer{margin:0 16px 14px;padding:12px;border:1px solid #dbe6ed;border-radius:16px;background:#fff;box-shadow:0 3px 18px #41638608;transition:box-shadow .2s,border-color .2s}.composer:focus-within{border-color:#8dbfc9;box-shadow:0 0 0 3px #81c4d019,0 5px 22px #6574ba10}.composer-label{display:block;margin:0 2px 7px;font-size:11px;font-weight:600;color:#548194}.composer-label>span{font-weight:400;color:#8c9aaa}.composer :deep(.el-textarea__inner){box-shadow:none!important;resize:none;padding:4px 3px;background:transparent;color:#33465d}.composer :deep(.el-input__count){background:transparent;font-size:10px}.composer-actions{font-size:10px}.composer-actions>.el-button{border:0;border-radius:10px;background:linear-gradient(120deg,#258fa3,#6473be);box-shadow:0 3px 10px #477d9e20}.composer-actions>.el-button:not(:disabled):hover{filter:brightness(1.08)}
.gilo-message-enter-active{transition:opacity .24s ease,transform .24s ease}.gilo-message-enter-from{opacity:0;transform:translateY(8px)}@keyframes gilo-signal{50%{height:20px;opacity:.55}}
@media(max-width:768px){.gilo-heading{gap:9px}.gilo-heading>.gilo-avatar{width:34px;height:34px}.coach-chat-header h1{font-size:18px}.coach-chat-header .gilo-tagline{display:none}.coach-chat-header .eyebrow{font-size:9px;letter-spacing:0}.coach-chat-layout{border-radius:15px;box-shadow:none}.message-list{gap:18px}.message-content{font-size:14px;line-height:1.8}.message-bubble{padding:11px 12px}.composer{margin:0 8px 8px;padding:9px;border-radius:13px}.composer-label{font-size:10px}.composer-label>span{display:none}.composer :deep(.el-textarea__inner){font-size:16px}.empty-chat{padding:8px}.is-short-viewport .composer-label{display:none}.is-short-viewport .gilo-heading>.gilo-avatar{width:26px;height:26px}}
@media(prefers-reduced-motion:reduce){.coach-chat-page *,.coach-chat-page :deep(*){animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style>
