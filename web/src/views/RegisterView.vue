<template>
  <main class="auth-page">
    <section class="auth-intro">
      <div class="auth-mark">GL</div>
      <h1>创建训练账号</h1>
      <p>账号只用于隔离你的训练周期、训练块、计划、日志和配速规则。</p>
    </section>

    <section class="auth-panel">
      <h2>注册</h2>
      <p class="auth-hint">暂不做邮箱验证，邮箱可留空。</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model.trim="form.username" autocomplete="username" placeholder="至少 3 位" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model.trim="form.nickname" placeholder="用于顶部显示，可留空" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model.trim="form.email" autocomplete="email" placeholder="可选" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            autocomplete="new-password"
            placeholder="至少 8 位"
            show-password
            type="password"
          />
        </el-form-item>
        <el-button class="auth-submit" type="primary" :loading="loading" @click="handleRegister">
          注册并进入
        </el-button>
      </el-form>

      <div class="auth-switch">
        已有账号？
        <router-link to="/login">去登录</router-link>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
import { loginUser, registerUser, setStoredToken } from "@/api/auth";
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
</script>
