<template>
  <nav class="training-journey" aria-label="训练闭环">
    <router-link v-for="item in items" :key="item.step" :to="item.path" :aria-current="active === item.step ? 'step' : undefined" :class="{ current: active === item.step }">
      <span>{{ item.number }}</span><div><strong>{{ item.title }}</strong><small>{{ item.caption }}</small></div>
    </router-link>
  </nav>
</template>
<script setup lang="ts">
defineProps<{ active: "plan" | "train" | "record" | "review" }>();
const items = [
  { step: "plan", number: "01", title: "安排计划", caption: "先预览，再确认", path: "/training-plan" },
  { step: "train", number: "02", title: "执行训练", caption: "看今天的安排", path: "/today" },
  { step: "record", number: "03", title: "记录感受", caption: "同步与确认关联", path: "/data-sync" },
  { step: "review", number: "04", title: "复盘调整", caption: "修改须经你确认", path: "/weekly-review" },
];
</script>
<style scoped>
.training-journey{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.training-journey a{display:flex;align-items:center;gap:10px;padding:12px;color:var(--muted);border:1px solid var(--line-soft);border-radius:12px;background:var(--surface);text-decoration:none}.training-journey a.current{border-color:var(--primary);background:var(--el-color-primary-light-9)}.training-journey a>span{font-size:12px;font-weight:800;color:var(--primary)}.training-journey strong{display:block;font-size:13px;color:var(--text)}.training-journey small{font-size:11px}@media(max-width:640px){.training-journey{grid-template-columns:repeat(2,minmax(0,1fr))}.training-journey a{padding:9px}.training-journey small{display:none}}
</style>
