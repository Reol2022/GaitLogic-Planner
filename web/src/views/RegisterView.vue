<template>
  <main class="auth-page register-auth-page">
    <header class="register-topbar">
      <div class="register-brand">Gaitlogic</div>
    </header>

    <section class="register-stage">
      <div class="register-caption">
        <span>训练数据 · 个人隔离 · 长期复盘</span>
        <strong>创建账号，开始管理你的训练周期。</strong>
      </div>

      <section class="auth-panel register-panel">
        <h2>注册</h2>
        <div class="register-divider"></div>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model.trim="form.username"
              autocomplete="username"
              placeholder="至少 3 位"
              size="large"
            />
          </el-form-item>
          <el-form-item label="昵称" prop="nickname">
            <el-input v-model.trim="form.nickname" placeholder="用于顶部显示，可留空" size="large" />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model.trim="form.email" autocomplete="email" placeholder="可选" size="large" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              autocomplete="new-password"
              placeholder="至少 8 位"
              show-password
              size="large"
              type="password"
            />
          </el-form-item>
          <el-button class="auth-submit" type="primary" :loading="loading" size="large" @click="handleRegister">
            注册并进入
          </el-button>
        </el-form>

        <div class="auth-switch">
          已有账号？
          <router-link to="/login">去登录</router-link>
        </div>
      </section>
    </section>

    <footer class="register-footer">
      <span>Copyright © 2026 GaitLogic Planner</span>
      <span>严肃跑者训练计划与训练日志系统</span>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
import { loginUser, registerUser, setStoredToken } from "@/api/auth";
import { getSystemSettings } from "@/api/systemSettings";
import type { UserRegisterPayload } from "@/types/models";

const router = useRouter();
const formRef = ref<FormInstance>();
const loading = ref(false);
const form = reactive<UserRegisterPayload>({
  username: "",
  password: "",
  email: "",
  nickname: "",
});

const rules: FormRules = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 3, message: "用户名至少 3 位", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 8, message: "密码至少 8 位", trigger: "blur" },
  ],
  email: [{ type: "email", message: "邮箱格式不正确", trigger: "blur" }],
};

async function handleRegister() {
  await formRef.value?.validate();
  loading.value = true;
  try {
    const payload = {
      ...form,
      email: form.email || null,
      nickname: form.nickname || null,
    };
    await registerUser(payload);
    const token = await loginUser({ username: form.username, password: form.password });
    setStoredToken(token.access_token);
    ElMessage.success("注册成功");
    router.push("/");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  const settings = await getSystemSettings();
  if (!settings.allow_public_registration) {
    ElMessage.warning("当前系统已关闭公开注册，请联系管理员创建账号。");
    router.replace("/login");
  }
});
</script>

<style scoped>
.register-auth-page {
  position: relative;
  display: block;
  min-height: 100vh;
  overflow: auto;
  background:
    linear-gradient(90deg, rgba(4, 10, 18, 0.2), rgba(10, 19, 34, 0.36)),
    url("../assets/login-runner-bg.png") center / cover no-repeat;
}

.register-auth-page::after {
  position: absolute;
  inset: 68px 0 0;
  pointer-events: none;
  content: "";
  background:
    linear-gradient(90deg, rgba(5, 12, 22, 0.08) 0%, rgba(5, 12, 22, 0.18) 46%, rgba(5, 12, 22, 0.34) 100%),
    linear-gradient(0deg, rgba(3, 7, 12, 0.28), transparent 34%);
}

.register-topbar {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  height: 70px;
  padding: 0 24px;
  background: #151515;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06);
}

.register-brand {
  color: #ffffff;
  font-size: 34px;
  font-weight: 300;
  letter-spacing: -1px;
  line-height: 1;
}

.register-stage {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 494px minmax(24px, 0.72fr);
  min-height: calc(100vh - 118px);
  padding-top: 34px;
}

.register-caption {
  align-self: end;
  max-width: 520px;
  margin: 0 0 74px clamp(24px, 5vw, 82px);
  color: #ffffff;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.36);
}

.register-caption span {
  display: block;
  margin-bottom: 12px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  font-weight: 700;
}

.register-caption strong {
  display: block;
  font-size: clamp(28px, 3vw, 44px);
  font-weight: 760;
  line-height: 1.16;
}

.register-panel {
  align-self: start;
  width: 100%;
  margin: 0;
  padding: 30px 34px 28px;
  border: 0;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 16px 38px rgba(0, 0, 0, 0.28);
}

.register-panel h2 {
  color: #05070a;
  font-size: 28px;
  font-weight: 500;
  letter-spacing: 0;
}

.register-divider {
  height: 1px;
  margin: 16px 0;
  background: #e9e2d4;
}

.register-panel :deep(.el-form-item) {
  margin-bottom: 15px;
}

.register-panel :deep(.el-form-item__label) {
  color: #05070a;
  font-size: 15px;
  font-weight: 760;
}

.register-panel :deep(.el-input__wrapper) {
  border-radius: 2px;
  background: #eef4ff;
  box-shadow: 0 0 0 1px #d3dbe8 inset;
}

.register-panel :deep(.el-input__wrapper.is-focus) {
  background: #ffffff;
  box-shadow: 0 0 0 1px #1976d2 inset;
}

.register-panel .auth-submit {
  width: 100%;
  height: 42px;
  margin-top: 6px;
  border-radius: 3px;
  font-size: 16px;
}

.register-panel .auth-switch {
  margin-top: 18px;
  color: #05070a;
  font-size: 15px;
  text-align: center;
}

.register-panel .auth-switch a {
  color: #05070a;
  font-weight: 500;
  text-decoration: underline;
}

.register-footer {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 0 24px;
  background: #050505;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
}

@media (max-width: 980px) {
  .register-stage {
    display: flex;
    justify-content: center;
    min-height: calc(100vh - 118px);
    padding: 34px 18px;
  }

  .register-caption {
    display: none;
  }

  .register-panel {
    max-width: 494px;
  }
}

@media (max-width: 560px) {
  .register-topbar {
    height: 62px;
  }

  .register-brand {
    font-size: 28px;
  }

  .register-stage {
    min-height: calc(100vh - 132px);
    padding: 24px 14px;
  }

  .register-panel {
    padding: 24px 20px;
  }

  .register-footer {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
    padding: 12px 16px;
  }
}
</style>
