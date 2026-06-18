<template>
  <main class="auth-page login-auth-page">
    <header class="login-topbar">
      <div class="login-brand">Gaitlogic</div>
    </header>

    <section class="login-stage">
      <div class="login-caption">
        <span>训练计划 · 日志 · 配速</span>
        <strong>把每一周训练，变成可追踪的进步。</strong>
      </div>

      <section class="auth-panel login-panel">
        <h2>登录</h2>
        <div class="login-divider"></div>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model.trim="form.username"
              autocomplete="username"
              placeholder="请输入用户名"
              size="large"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              autocomplete="current-password"
              placeholder="请输入密码"
              show-password
              size="large"
              type="password"
            />
          </el-form-item>
          <div class="login-options">
            <el-checkbox :model-value="true">保持登录状态</el-checkbox>
            <span>忘记密码请联系管理员</span>
          </div>
          <el-button class="auth-submit" type="primary" :loading="loading" size="large" @click="handleLogin">
            登录
          </el-button>
        </el-form>

        <div v-if="allowPublicRegistration" class="auth-switch">
          还没有账号？
          <router-link to="/register">立即注册</router-link>
        </div>
      </section>
    </section>

    <footer class="login-footer">
      <span>Copyright © 2026 GaitLogic Planner</span>
      <span>严肃跑者训练计划与训练日志系统</span>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
import { loginUser, setStoredToken } from "@/api/auth";
import { getSystemSettings } from "@/api/systemSettings";
import type { UserLoginPayload } from "@/types/models";
import { getCachedAllowPublicRegistration } from "@/utils/systemSettingsCache";

const router = useRouter();
const route = useRoute();
const formRef = ref<FormInstance>();
const loading = ref(false);
const allowPublicRegistration = ref(getCachedAllowPublicRegistration());
const form = reactive<UserLoginPayload>({
  username: "",
  password: "",
});

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 8, message: "密码至少 8 位", trigger: "blur" },
  ],
};

async function handleLogin() {
  await formRef.value?.validate();
  loading.value = true;
  try {
    const token = await loginUser(form);
    setStoredToken(token.access_token);
    ElMessage.success("登录成功");
    router.push(String(route.query.redirect || "/"));
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const settings = await getSystemSettings();
    allowPublicRegistration.value = settings.allow_public_registration;
  } catch {
    allowPublicRegistration.value = getCachedAllowPublicRegistration();
  }
});
</script>

<style scoped>
.login-auth-page {
  position: relative;
  display: block;
  min-height: 100vh;
  overflow: hidden;
  background:
    linear-gradient(90deg, rgba(4, 10, 18, 0.22), rgba(10, 19, 34, 0.34)),
    url("../assets/login-runner-bg.png") center / cover no-repeat;
}

.login-auth-page::after {
  position: absolute;
  inset: 68px 0 0;
  pointer-events: none;
  content: "";
  background:
    linear-gradient(90deg, rgba(5, 12, 22, 0.08) 0%, rgba(5, 12, 22, 0.18) 46%, rgba(5, 12, 22, 0.3) 100%),
    linear-gradient(0deg, rgba(3, 7, 12, 0.28), transparent 34%);
}

.login-topbar {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  height: 70px;
  padding: 0 24px;
  background: #151515;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06);
}

.login-brand {
  color: #ffffff;
  font-size: 34px;
  font-weight: 300;
  letter-spacing: -1px;
  line-height: 1;
}

.login-stage {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 494px minmax(24px, 0.72fr);
  min-height: calc(100vh - 118px);
  padding-top: 34px;
}

.login-caption {
  align-self: end;
  max-width: 520px;
  margin: 0 0 74px clamp(24px, 5vw, 82px);
  color: #ffffff;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.36);
}

.login-caption span {
  display: block;
  margin-bottom: 12px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  font-weight: 700;
}

.login-caption strong {
  display: block;
  font-size: clamp(28px, 3vw, 44px);
  font-weight: 760;
  line-height: 1.16;
}

.login-panel {
  align-self: start;
  width: 100%;
  margin: 0;
  padding: 34px 34px 30px;
  border: 0;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 16px 38px rgba(0, 0, 0, 0.28);
}

.login-panel h2 {
  color: #05070a;
  font-size: 28px;
  font-weight: 500;
  letter-spacing: 0;
}

.login-divider {
  height: 1px;
  margin: 18px 0;
  background: #e9e2d4;
}

.login-panel :deep(.el-form-item__label) {
  color: #05070a;
  font-size: 15px;
  font-weight: 760;
}

.login-panel :deep(.el-input__wrapper) {
  border-radius: 2px;
  background: #eef4ff;
  box-shadow: 0 0 0 1px #d3dbe8 inset;
}

.login-panel :deep(.el-input__wrapper.is-focus) {
  background: #ffffff;
  box-shadow: 0 0 0 1px #1976d2 inset;
}

.login-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 2px 0 28px;
  color: #333b48;
  font-size: 14px;
}

.login-options span {
  color: #4b5563;
}

.login-panel .auth-submit {
  height: 42px;
  border-radius: 3px;
  font-size: 16px;
}

.login-panel .auth-switch {
  color: #05070a;
  font-size: 15px;
}

.login-panel .auth-switch a {
  color: #05070a;
  font-weight: 500;
  text-decoration: underline;
}

.login-footer {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 24px;
  background: #050505;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
}

@media (max-width: 980px) {
  .login-stage {
    display: flex;
    justify-content: center;
    min-height: calc(100vh - 118px);
    padding: 34px 18px;
  }

  .login-caption {
    display: none;
  }

  .login-panel {
    max-width: 494px;
  }
}

@media (max-width: 560px) {
  .login-topbar {
    height: 62px;
  }

  .login-brand {
    font-size: 28px;
  }

  .login-stage {
    min-height: calc(100vh - 132px);
    padding: 24px 14px;
  }

  .login-panel {
    padding: 26px 20px 24px;
  }

  .login-options,
  .login-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .login-footer {
    height: auto;
    gap: 6px;
    padding: 12px 16px;
  }
}
</style>
