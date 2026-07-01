<template>
  <footer class="site-filing-footer" :class="{ 'site-filing-footer--dark': variant === 'dark' }">
    <span>Copyright © 2026 GaitLogic Planner</span>
    <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
      蜀ICP备2022009555号
    </a>
    <a
      href="https://www.beian.gov.cn/portal/registerSystemInfo?recordcode=51070302110743"
      target="_blank"
      rel="noopener noreferrer"
    >
      川公网安备51070302110743号
    </a>
  </footer>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "light" | "dark";
  }>(),
  {
    variant: "light",
  },
);
</script>

<style scoped>
.site-filing-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 14px 18px;
  color: #667085;
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

.site-filing-footer a {
  color: inherit;
  text-decoration: none;
}

.site-filing-footer a:hover {
  color: #1976d2;
  text-decoration: underline;
}

.site-filing-footer--dark {
  color: #ffffff;
  background: #050505;
  font-weight: 700;
}

.site-filing-footer--dark a:hover {
  color: #d7ebff;
}

@media (max-width: 560px) {
  .site-filing-footer {
    align-items: center;
    flex-direction: column;
    gap: 4px;
  }
}
</style>
