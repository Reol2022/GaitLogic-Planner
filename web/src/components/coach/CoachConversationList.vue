<template>
  <section class="conversation-list" aria-label="Coach 对话列表">
    <div class="conversation-heading">
      <div class="heading-icon"><ChatDotRound /></div>
      <div>
        <strong>训练对话</strong>
        <span>继续之前的分析</span>
      </div>
    </div>

    <el-button type="primary" class="new-conversation" @click="$emit('create')">
      <el-icon><Plus /></el-icon>
      新建对话
    </el-button>

    <div class="conversation-section-label">
      <span>最近对话</span>
      <span class="conversation-count">{{ items.length }}</span>
    </div>

    <div v-if="loading" class="conversation-loading" aria-label="正在加载对话">
      <el-skeleton v-for="index in 3" :key="index" :rows="1" animated />
    </div>

    <div v-else-if="!items.length" class="conversation-empty">
      <ChatLineRound />
      <strong>还没有训练对话</strong>
      <span>新建对话，开始分析你的训练。</span>
    </div>

    <div v-else class="conversation-items">
      <article
        v-for="item in items"
        :key="item.id"
        class="conversation-item"
        :class="{ active: item.id === activeId }"
      >
        <button class="conversation-select" type="button" @click="$emit('select', item.id)">
          <span class="conversation-avatar"><ChatLineRound /></span>
          <span class="conversation-copy">
            <strong :title="item.title">{{ item.title }}</strong>
            <span class="conversation-meta">
              <span>{{ formatConversationTime(item.last_message_at || item.updated_at) }}</span>
              <span class="meta-dot" aria-hidden="true"></span>
              <span>{{ item.message_count }} 条消息</span>
            </span>
          </span>
        </button>

        <div class="conversation-actions">
          <button
            type="button"
            class="conversation-action"
            title="重命名会话"
            aria-label="重命名会话"
            @click.stop="$emit('rename', item.id, item.title)"
          >
            <EditPen />
          </button>
          <button
            v-if="item.status === 'active'"
            type="button"
            class="conversation-action"
            title="归档会话"
            aria-label="归档会话"
            @click.stop="$emit('archive', item.id)"
          >
            <FolderOpened />
          </button>
          <button
            type="button"
            class="conversation-action danger"
            title="删除会话"
            aria-label="删除会话"
            @click.stop="$emit('delete', item.id)"
          >
            <Delete />
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ChatDotRound, ChatLineRound, Delete, EditPen, FolderOpened, Plus } from "@element-plus/icons-vue";
import type { CoachConversation } from "@/types/coachAgent";

defineProps<{
  items: CoachConversation[];
  activeId?: string;
  loading?: boolean;
}>();

defineEmits<{
  create: [];
  select: [id: string];
  rename: [id: string, currentTitle: string];
  archive: [id: string];
  delete: [id: string];
}>();

const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function formatConversationTime(value?: string | null): string {
  if (!value) return "刚刚";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "最近" : dateTimeFormatter.format(parsed);
}
</script>

<style scoped>
.conversation-list { display: flex; min-height: 100%; flex-direction: column; gap: 14px; }
.conversation-heading { display: flex; align-items: center; gap: 10px; padding: 2px 3px 0; }
.heading-icon { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 11px; color: var(--el-color-primary); background: linear-gradient(145deg, var(--el-color-primary-light-8), var(--el-color-primary-light-9)); }
.heading-icon svg { width: 18px; height: 18px; }
.conversation-heading strong, .conversation-heading span { display: block; }
.conversation-heading strong { color: var(--el-text-color-primary); font-size: 14px; line-height: 1.3; }
.conversation-heading span { margin-top: 2px; color: var(--el-text-color-secondary); font-size: 11px; }
.new-conversation { width: 100%; height: 40px; margin: 0; border: 0; border-radius: 11px; box-shadow: 0 8px 18px color-mix(in srgb, var(--el-color-primary) 20%, transparent); }
.new-conversation :deep(.el-icon) { margin-right: 5px; }
.conversation-section-label { display: flex; align-items: center; justify-content: space-between; padding: 0 4px; color: var(--el-text-color-secondary); font-size: 11px; font-weight: 600; letter-spacing: .04em; }
.conversation-count { display: grid; min-width: 22px; height: 20px; place-items: center; border-radius: 10px; background: var(--el-fill-color); font-variant-numeric: tabular-nums; }
.conversation-loading { display: grid; gap: 10px; padding: 4px; }
.conversation-empty { display: grid; place-items: center; gap: 7px; margin-top: 12px; padding: 24px 14px; border: 1px dashed var(--el-border-color); border-radius: 14px; color: var(--el-text-color-secondary); text-align: center; }
.conversation-empty svg { width: 28px; color: var(--el-text-color-placeholder); }
.conversation-empty strong { color: var(--el-text-color-regular); font-size: 13px; }
.conversation-empty span { font-size: 12px; line-height: 1.5; }
.conversation-items { display: grid; gap: 7px; }
.conversation-item { position: relative; display: flex; min-width: 0; align-items: center; border: 1px solid transparent; border-radius: 12px; transition: border-color .18s ease, background-color .18s ease, box-shadow .18s ease, transform .18s ease; }
.conversation-item:hover { border-color: var(--el-border-color-light); background: var(--el-bg-color); transform: translateY(-1px); }
.conversation-item.active { border-color: color-mix(in srgb, var(--el-color-primary) 26%, transparent); background: var(--el-color-primary-light-9); box-shadow: inset 3px 0 0 var(--el-color-primary); }
.conversation-select { display: flex; min-width: 0; flex: 1; align-items: center; gap: 9px; padding: 10px 82px 10px 10px; border: 0; color: inherit; background: transparent; text-align: left; cursor: pointer; }
.conversation-avatar { display: grid; width: 30px; height: 30px; flex: 0 0 30px; place-items: center; border-radius: 10px; color: var(--el-text-color-secondary); background: var(--el-fill-color-light); }
.conversation-avatar svg { width: 15px; height: 15px; }
.active .conversation-avatar { color: var(--el-color-primary); background: var(--el-color-primary-light-8); }
.conversation-copy { min-width: 0; flex: 1; }
.conversation-copy strong { display: block; overflow: hidden; color: var(--el-text-color-primary); font-size: 13px; font-weight: 600; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
.conversation-meta { display: flex; min-width: 0; align-items: center; gap: 5px; margin-top: 4px; overflow: hidden; color: var(--el-text-color-secondary); font-size: 10px; white-space: nowrap; }
.meta-dot { width: 3px; height: 3px; flex: 0 0 3px; border-radius: 50%; background: var(--el-border-color); }
.conversation-actions { position: absolute; right: 7px; display: flex; gap: 2px; opacity: 0; transform: translateX(3px); transition: opacity .18s ease, transform .18s ease; }
.conversation-item:hover .conversation-actions, .conversation-item:focus-within .conversation-actions, .conversation-item.active .conversation-actions { opacity: 1; transform: translateX(0); }
.conversation-action { display: grid; width: 24px; height: 24px; place-items: center; padding: 5px; border: 0; border-radius: 7px; color: var(--el-text-color-secondary); background: color-mix(in srgb, var(--el-bg-color) 88%, transparent); cursor: pointer; }
.conversation-action:hover { color: var(--el-color-primary); background: var(--el-color-primary-light-8); }
.conversation-action.danger:hover { color: var(--el-color-danger); background: var(--el-color-danger-light-9); }
.conversation-action svg { width: 14px; height: 14px; }
@media (hover: none) { .conversation-actions { opacity: 1; transform: none; } }
</style>
