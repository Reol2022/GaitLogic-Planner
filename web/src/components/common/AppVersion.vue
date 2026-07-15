<template>
  <span class="app-version" :class="{ 'app-version--compact': compact }">
    {{ showStage ? APP_VERSION_LABEL : `v${APP_VERSION}` }}
  </span>
</template>

<script setup lang="ts">
import { APP_VERSION, APP_VERSION_LABEL } from "@/config/app";

withDefaults(
  defineProps<{
    compact?: boolean;
    showStage?: boolean;
  }>(),
  {
    compact: false,
    showStage: true,
  },
);
</script>

<style scoped>
.app-version {
  color: var(--muted, #9aa4af);
  font-size: 11px;
  font-weight: 400;
  line-height: 1.2;
  opacity: 0.74;
  white-space: nowrap;
}

.app-version--compact {
  font-size: 10px;
  opacity: 0.68;
}
</style>
