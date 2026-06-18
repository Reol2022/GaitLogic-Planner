<template>
  <el-dialog
    v-model="visible"
    class="auth-dialog"
    width="420px"
    :close-on-click-modal="false"
    :show-close="false"
    append-to-body
  >
    <template #header>
      <div class="auth-dialog-head">
        <span>GaitLogic Planner</span>
        <strong>{{ activeTab === "login" ? "登录后继续" : "创建账号" }}</strong>
      </div>
    </template>

    <el-tabs v-model="activeTab" stretch>
      <el-tab-pane label="登录" name="login">
        <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top" @submit.prevent>
          <el-form-item label="用户名" prop="username">
            <el-input v-model.trim="loginForm.username" autocomplete="username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              autocomplete="current-password"
              placeholder="请输入密码"
              show-password
              type="password"
            />
          </el-form-item>
          <el-button type="primary" class="auth-dialog-submit" :loading="loading" @click="handleLogin">
            登录
          </el-button>
        </el-form>
      </el-tab-pane>

      <el-tab-pane v-if="allowPublicRegistration" label="注册" name="register">
        <el-form
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          label-position="top"
          @submit.prevent
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model.trim="registerForm.username" autocomplete="username" placeholder="至少 3 位" />
          </el-form-item>
          <el-form-item label="昵称" prop="nickname">
            <el-input v-model.trim="registerForm.nickname" placeholder="可选" />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model.trim="registerForm.email" autocomplete="email" placeholder="可选" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="registerForm.password"
              autocomplete="new-password"
              placeholder="至少 8 位"
              show-password
              type="password"
            />
          </el-form-item>
          <el-button type="primary" class="auth-dialog-submit" :loading="loading" @click="handleRegister">
            注册并进入
          </el-button>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <div class="auth-dialog-note">
      登录只用于保存你的训练计划、日志和配速规则
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";

import { loginUser, registerUser, setStoredToken } from "@/api/auth";
import { getSystemSettings } from "@/api/systemSettings";
import type { UserLoginPayload, UserRegisterPayload } from "@/types/models";
import { AUTH_REQUIRED_EVENT, type AuthRequiredDetail } from "@/utils/authPrompt";
import { getCachedAllowPublicRegistration } from "@/utils/systemSettingsCache";

const visible = ref(false);
const loading = ref(false);
const activeTab = ref<"login" | "register">("login");
const redirectPath = ref("/today");
const allowPublicRegistration = ref(getCachedAllowPublicRegistration());
const loginFormRef = ref<FormInstance>();
const registerFormRef = ref<FormInstance>();
const loginForm = reactive<UserLoginPayload>({
  username: "",
  password: "",
});
const registerForm = reactive<UserRegisterPayload>({
  username: "",
  password: "",
  email: "",
  nickname: "",
});

const loginRules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 8, message: "密码至少 8 位", trigger: "blur" },
  ],
};

const registerRules: FormRules = {
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

function normalizeRedirect(value?: string) {
  if (!value || value === "/login" || value === "/register") return "/today";
  return value;
}

function openAuthDialog(event: Event) {
  const detail = (event as CustomEvent<AuthRequiredDetail>).detail;
  redirectPath.value = normalizeRedirect(detail?.redirect);
  activeTab.value = "login";
  visible.value = true;
}

async function refreshSettings() {
  try {
    const settings = await getSystemSettings();
    allowPublicRegistration.value = settings.allow_public_registration;
  } catch {
    allowPublicRegistration.value = getCachedAllowPublicRegistration();
  }
}

function finishAuth() {
  visible.value = false;
  window.location.href = redirectPath.value;
}

async function handleLogin() {
  await loginFormRef.value?.validate();
  loading.value = true;
  try {
    const token = await loginUser(loginForm);
    setStoredToken(token.access_token);
    ElMessage.success("登录成功");
    finishAuth();
  } finally {
    loading.value = false;
  }
}

async function handleRegister() {
  await registerFormRef.value?.validate();
  loading.value = true;
  try {
    await registerUser({
      ...registerForm,
      email: registerForm.email || null,
      nickname: registerForm.nickname || null,
    });
    const token = await loginUser({ username: registerForm.username, password: registerForm.password });
    setStoredToken(token.access_token);
    ElMessage.success("注册成功");
    finishAuth();
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  refreshSettings();
  window.addEventListener(AUTH_REQUIRED_EVENT, openAuthDialog);
});

onBeforeUnmount(() => {
  window.removeEventListener(AUTH_REQUIRED_EVENT, openAuthDialog);
});
</script>

<style scoped>
.auth-dialog-head {
  display: grid;
  gap: 4px;
}

.auth-dialog-head span {
  color: #1976d2;
  font-size: 13px;
  font-weight: 700;
}

.auth-dialog-head strong {
  color: #172033;
  font-size: 22px;
}

.auth-dialog-submit {
  width: 100%;
}

.auth-dialog-note {
  margin-top: 14px;
  color: #667085;
  font-size: 12px;
  line-height: 1.6;
}

:global(.auth-dialog .el-dialog__body) {
  padding-top: 8px;
}
</style>
