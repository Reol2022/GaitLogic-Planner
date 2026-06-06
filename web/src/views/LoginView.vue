<template>
  <main class="auth-page">
    <section class="auth-intro">
      <div class="auth-mark">GL</div>
      <h1>GaitLogic Planner</h1>
      <p>为严肃跑者整理训练计划、每日执行和复盘数据。</p>
    </section>

    <section class="auth-panel">
      <h2>登录</h2>
      <p class="auth-hint">进入你的训练工作台。</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model.trim="form.username" autocomplete="username" placeholder="输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            autocomplete="current-password"
            placeholder="输入密码"
            show-password
            type="password"
          />
        </el-form-item>
        <el-button class="auth-submit" type="primary" :loading="loading" @click="handleLogin">
          登录
        </el-button>
      </el-form>

      <div class="auth-switch">
        还没有账号？
        <router-link to="/register">立即注册</router-link>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
import { loginUser, setStoredToken } from "@/api/auth";
import type { UserLoginPayload } from "@/types/models";

const router = useRouter();
const route = useRoute();
const formRef = ref<FormInstance>();
const loading = ref(false);
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
</script>
