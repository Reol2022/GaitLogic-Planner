<template>
  <aside
    v-if="status"
    class="knowledge-status"
    :class="`tone-${display?.tone}`"
    role="status"
    aria-label="训练知识检索状态"
  >
    <strong>{{ display?.label }}</strong>
    <span>{{ display?.description }}</span>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { CoachKnowledgeStatus } from "@/types/coachAgent";
import { coachKnowledgeStatusDisplay } from "@/utils/coachAgentDisplay";

const props = defineProps<{ status: CoachKnowledgeStatus | null }>();
const display = computed(() => (
  props.status ? coachKnowledgeStatusDisplay[props.status] : null
));
</script>

<style scoped>
.knowledge-status {
  display: grid;
  gap: 3px;
  min-width: 0;
  padding: 11px 14px;
  border: 1px solid #d8e2ec;
  border-radius: 8px;
  background: #f8fafc;
}
strong { color: #26354a; font-size: 13px; }
span { color: #5e6b7c; font-size: 12px; line-height: 1.55; }
.tone-positive { border-color: #b9ddca; background: #f3fbf6; }
.tone-notice { border-color: #ead39d; background: #fffaf0; }
</style>
