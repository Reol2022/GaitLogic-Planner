<template>
  <el-button
    class="save-state-button"
    :icon="CollectionTag"
    :loading="loading"
    :disabled="loading"
    @click="$emit('save')"
  >保存今日状态</el-button>
</template>

<script setup lang="ts">
import { CollectionTag } from "@element-plus/icons-vue";
defineProps<{ loading: boolean }>();
defineEmits<{ save: [] }>();
</script>

<style scoped>
.save-state-button { min-height: 40px; }
</style>
