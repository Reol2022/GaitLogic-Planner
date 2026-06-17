<template>
  <main class="not-found-page">
    <section class="not-found-card">
      <span>404</span>
      <h1>页面不存在</h1>
      <p>你访问的页面可能已移动、删除，或者地址输入有误。</p>
      <div>
        <el-button type="primary" @click="router.push('/today')">回到今日训练</el-button>
        <el-button @click="router.back()">返回上一页</el-button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<style scoped>
.not-found-page {
  display: grid;
  min-height: calc(100vh - 120px);
  place-items: center;
  padding: 32px;
}

.not-found-card {
  width: min(520px, 100%);
  padding: 38px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: #ffffff;
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.not-found-card span {
  color: #1976d2;
  font-size: 58px;
  font-weight: 800;
  line-height: 1;
}

.not-found-card h1 {
  margin: 14px 0 0;
  color: #172033;
  font-size: 26px;
}

.not-found-card p {
  margin: 10px 0 24px;
  color: #667085;
}

.not-found-card div {
  display: flex;
  justify-content: center;
  gap: 10px;
}

@media (max-width: 560px) {
  .not-found-card {
    padding: 28px 20px;
  }

  .not-found-card div {
    flex-direction: column;
  }
}
</style>
