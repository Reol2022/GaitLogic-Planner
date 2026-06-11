<template>
  <div class="page-stack admin-system-page">
    <section class="admin-hero">
      <div>
        <span>Admin Console</span>
        <h2>系统设置</h2>
        <p>集中查看当前系统能力和管理入口。需要持久化的新开关后续可继续放在这里。</p>
      </div>
    </section>

    <section class="settings-grid">
      <article class="panel">
        <div class="panel-head">
          <h3>账号与权限</h3>
          <p>当前系统使用账号角色控制后台权限，管理员可维护用户角色和状态。</p>
        </div>
        <el-button type="primary" @click="router.push('/admin/users')">进入用户管理</el-button>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>AI 生成</h3>
          <p>模型、Base URL、API Key、额度、冷却时间和生成参数统一在模型设置中配置。</p>
        </div>
        <el-button type="primary" @click="router.push('/admin/ai-settings')">进入 AI 模型设置</el-button>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>训练数据范围</h3>
          <p>当前项目仍聚焦训练计划、训练日志、配速规则、复盘统计和 AI 课表草稿。</p>
        </div>
        <el-tag effect="light">Garmin / App / 商业化未启用</el-tag>
      </article>

      <article class="panel">
        <div class="panel-head">
          <h3>安全提示</h3>
          <p>停用用户后，该用户无法继续登录；已登录令牌会在下一次鉴权时被状态检查拦截。</p>
        </div>
        <el-tag type="warning" effect="light">管理员请至少保留一个 active admin</el-tag>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<style scoped>
.admin-hero {
  padding: 22px;
}

.admin-hero span {
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.admin-hero h2 {
  margin: 6px 0 0;
  color: #172033;
}

.admin-hero p,
.panel-head p {
  margin: 6px 0 0;
  color: #667085;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  display: grid;
  align-content: space-between;
  gap: 18px;
  padding: 22px;
}

.panel-head h3 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
