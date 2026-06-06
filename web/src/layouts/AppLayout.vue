<template>
  <el-container class="app-shell">
    <el-aside width="232px" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">GL</div>
        <div>
          <div class="brand-name">Gaitlogic</div>
          <div class="brand-subtitle">夏训执行工作簿</div>
        </div>
      </div>

      <el-menu :default-active="route.path" router class="side-menu">
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>Dashboard</span>
        </el-menu-item>
        <el-menu-item index="/cycles">
          <el-icon><Calendar /></el-icon>
          <span>训练周期</span>
        </el-menu-item>
        <el-menu-item index="/blocks">
          <el-icon><Grid /></el-icon>
          <span>训练块</span>
        </el-menu-item>
        <el-menu-item index="/workouts">
          <el-icon><List /></el-icon>
          <span>训练计划</span>
        </el-menu-item>
        <el-menu-item index="/today">
          <el-icon><Timer /></el-icon>
          <span>今日训练</span>
        </el-menu-item>
        <el-menu-item index="/pace-rules">
          <el-icon><Odometer /></el-icon>
          <span>配速规则</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h1>{{ pageTitle }}</h1>
          <p>严飞夏训计划与训练日志 · 后台录入与复盘</p>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import {
  Calendar,
  DataAnalysis,
  Grid,
  List,
  Odometer,
  Timer,
} from "@element-plus/icons-vue";

const route = useRoute();
const pageTitle = computed(() => String(route.meta.title || "Dashboard"));
</script>
