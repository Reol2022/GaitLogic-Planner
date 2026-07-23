<template>
  <details v-if="tools.length" class="tool-summary">
    <summary>本次参考的数据（{{ tools.length }} 项）</summary>
    <ul>
      <li v-for="(tool, index) in tools" :key="`${tool.tool_name}-${index}`">
        <span>{{ coachToolName(tool.tool_name) }}</span>
        <strong :class="`tone-${coachToolStatusDisplay[tool.status].tone}`">
          {{ coachToolStatusDisplay[tool.status].label }}
        </strong>
        <small v-if="tool.safe_error_code">{{ tool.safe_error_code }}</small>
      </li>
    </ul>
  </details>
</template>

<script setup lang="ts">
import type { CoachToolCallSummary } from "@/types/coachAgent";
import { coachToolName, coachToolStatusDisplay } from "@/utils/coachAgentDisplay";

withDefaults(defineProps<{ tools?: CoachToolCallSummary[] }>(), {
  tools: () => [],
});
</script>

<style scoped>
.tool-summary { min-width: 0; padding: 13px 15px; border: 1px solid var(--card-border); border-radius: var(--card-radius); background: #fff; }
summary { cursor: pointer; color: #344054; font-size: 14px; font-weight: 700; }
summary:focus-visible { outline: 3px solid rgba(25, 118, 210, .3); outline-offset: 4px; }
ul { display: grid; gap: 8px; margin: 13px 0 0; padding: 0; list-style: none; }
li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 12px; padding: 9px 10px; border-radius: 6px; background: #f7f9fb; }
li span { overflow-wrap: anywhere; color: #344054; }
li strong { font-size: 12px; }
li small { grid-column: 1 / -1; overflow-wrap: anywhere; color: #667085; }
.tone-positive { color: #207044; }
.tone-notice { color: #8a5b0b; }
.tone-attention { color: #9f352e; }
.tone-neutral { color: #667085; }
</style>
