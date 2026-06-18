<template>
  <div class="page-stack admin-users-page">
    <PageHeader title="用户管理" subtitle="查看账号、角色和状态。修改后会影响用户下一次请求的权限判断。">
      <template #actions><el-button :icon="Refresh" @click="loadUsers">刷新</el-button></template>
    </PageHeader>

    <div class="toolbar">
      <div class="filter-row">
        <el-input v-model="keyword" placeholder="搜索用户名 / 邮箱 / 昵称" clearable style="width: 280px" />
        <el-button :icon="Search" @click="loadUsers">查询</el-button>
      </div>
    </div>

    <section class="panel">
      <el-table :data="users" v-loading="loading" class="desktop-user-table">
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column prop="nickname" label="昵称" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="200" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" effect="light">
              {{ row.role === "admin" ? "管理员" : "用户" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'warning'" effect="light">
              {{ row.status === "active" ? "正常" : "已停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Edit" @click="openDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="mobile-user-list">
        <article v-for="user in users" :key="user.id" class="user-card">
          <div class="user-card-head">
            <div>
              <strong>{{ user.nickname || user.username }}</strong>
              <span>{{ user.username }}</span>
            </div>
            <el-tag :type="user.status === 'active' ? 'success' : 'warning'" effect="light">
              {{ user.status === "active" ? "正常" : "已停用" }}
            </el-tag>
          </div>
          <p>{{ user.email || "未填写邮箱" }}</p>
          <div class="user-card-actions">
            <el-tag :type="user.role === 'admin' ? 'danger' : 'info'" effect="light">
              {{ user.role === "admin" ? "管理员" : "用户" }}
            </el-tag>
            <el-button size="small" :icon="Edit" @click="openDialog(user)">编辑</el-button>
          </div>
        </article>
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="编辑用户" width="520px">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" disabled />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <div class="form-row">
          <el-form-item label="角色">
            <el-select v-model="form.role" style="width: 100%">
              <el-option label="用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width: 100%">
              <el-option label="正常" value="active" />
              <el-option label="停用" value="disabled" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Edit, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { listAdminUsers, updateAdminUser } from "@/api/admin";
import type { AdminUser } from "@/types/models";

const users = ref<AdminUser[]>([]);
const keyword = ref("");
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const editingId = ref<number | null>(null);
const form = reactive({
  username: "",
  email: "",
  nickname: "",
  role: "user" as "user" | "admin",
  status: "active" as "active" | "disabled",
});

async function loadUsers() {
  loading.value = true;
  try {
    users.value = await listAdminUsers(keyword.value);
  } finally {
    loading.value = false;
  }
}

function openDialog(user: AdminUser) {
  editingId.value = user.id;
  form.username = user.username;
  form.email = user.email || "";
  form.nickname = user.nickname || "";
  form.role = user.role === "admin" ? "admin" : "user";
  form.status = user.status === "disabled" ? "disabled" : "active";
  dialogVisible.value = true;
}

async function saveUser() {
  if (!editingId.value) return;
  saving.value = true;
  try {
    await updateAdminUser(editingId.value, {
      email: form.email || null,
      nickname: form.nickname || null,
      role: form.role,
      status: form.status,
    });
    ElMessage.success("用户已更新");
    dialogVisible.value = false;
    await loadUsers();
  } finally {
    saving.value = false;
  }
}

function formatDateTime(value?: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "-";
}

onMounted(loadUsers);
</script>

<style scoped>
.admin-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
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

.admin-hero p {
  margin: 6px 0 0;
  color: #667085;
}

.panel {
  padding: 0;
}

.mobile-user-list {
  display: none;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

@media (max-width: 768px) {
  .admin-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .desktop-user-table {
    display: none;
  }

  .mobile-user-list {
    display: grid;
    gap: 10px;
    padding: 12px;
  }

  .user-card {
    display: grid;
    gap: 10px;
    padding: 14px;
    border: 1px solid #d8dde3;
    border-radius: 6px;
  }

  .user-card-head,
  .user-card-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .user-card-head div {
    display: grid;
    gap: 3px;
  }

  .user-card-head span,
  .user-card p {
    margin: 0;
    color: #667085;
    font-size: 12px;
  }

  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
