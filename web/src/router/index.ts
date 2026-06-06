import { createRouter, createWebHistory } from "vue-router";
import { getStoredToken } from "@/api/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "Login",
      component: () => import("@/views/LoginView.vue"),
      meta: { title: "登录", public: true },
    },
    {
      path: "/register",
      name: "Register",
      component: () => import("@/views/RegisterView.vue"),
      meta: { title: "注册", public: true },
    },
    {
      path: "/",
      name: "Dashboard",
      component: () => import("@/views/DashboardView.vue"),
      meta: { title: "Dashboard" },
    },
    {
      path: "/cycles",
      name: "TrainingCycles",
      component: () => import("@/views/TrainingCyclesView.vue"),
      meta: { title: "训练周期" },
    },
    {
      path: "/blocks",
      name: "TrainingBlocks",
      component: () => import("@/views/TrainingBlocksView.vue"),
      meta: { title: "训练块" },
    },
    {
      path: "/workouts",
      name: "PlannedWorkouts",
      component: () => import("@/views/PlannedWorkoutsView.vue"),
      meta: { title: "训练计划" },
    },
    {
      path: "/today",
      name: "Today",
      component: () => import("@/views/TodayView.vue"),
      meta: { title: "今日训练" },
    },
    {
      path: "/workouts/:id/log",
      name: "WorkoutLogEdit",
      component: () => import("@/views/WorkoutLogEditView.vue"),
      meta: { title: "训练日志填写" },
    },
    {
      path: "/pace-rules",
      name: "PaceRules",
      component: () => import("@/views/PaceRulesView.vue"),
      meta: { title: "配速规则" },
    },
    {
      path: "/excel-import",
      name: "ExcelImport",
      component: () => import("@/views/ExcelImport.vue"),
      meta: { title: "Excel 导入" },
    },
  ],
});

router.beforeEach((to) => {
  const token = getStoredToken();

  if (!to.meta.public && !token) {
    return {
      path: "/login",
      query: { redirect: to.fullPath },
    };
  }

  if (to.meta.public && token) {
    return "/";
  }

  return true;
});

export default router;
