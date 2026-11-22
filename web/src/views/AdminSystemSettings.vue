<template>
  <section class="panel" style="padding:24px">
    <h2>系统设置已迁入管理控制台</h2>
    <p>请使用独立的管理员会话继续操作，跑者端登录状态不会自动转交后台。</p>
    <a :href="ADMIN_SYSTEM_SETTINGS_URL">进入后台系统设置 →</a>
  </section>
</template>
<script setup lang="ts">
import { onMounted } from 'vue';
import { ADMIN_SYSTEM_SETTINGS_URL } from '@/admin/navigation';
onMounted(() => window.location.replace(ADMIN_SYSTEM_SETTINGS_URL));
</script>
