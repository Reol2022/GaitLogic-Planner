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
      redirect: "/today",
    },
    {
      path: "/dashboard",
      name: "Dashboard",
      component: () => import("@/views/DashboardView.vue"),
      meta: { title: "训练统计" },
    },
    {
      path: "/today",
      name: "Today",
      component: () => import("@/views/TodayView.vue"),
      meta: { title: "今日训练" },
    },
    {
      path: "/training-calendar",
      name: "TrainingCalendar",
      component: () => import("@/views/TrainingCalendar.vue"),
      meta: { title: "训练日历" },
    },
    {
      path: "/ai-plan",
      name: "AIPlan",
      component: () => import("@/views/AIPlanGenerator.vue"),
      meta: { title: "AI 制定计划" },
    },
    {
      path: "/ai-coach-preference",
      name: "AICoachPreference",
      component: () => import("@/views/AICoachPreference.vue"),
      meta: { title: "AI 教练偏好" },
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
      meta: { title: "我的训练计划" },
    },
    {
      path: "/workouts/:id/log",
      name: "WorkoutLogEdit",
      component: () => import("@/views/WorkoutLogEditView.vue"),
      meta: { title: "训练日志填写" },
    },
    {
      path: "/pace-calculator",
      name: "PaceCalculator",
      component: () => import("@/views/PaceCalculator.vue"),
      meta: { title: "配速计算器" },
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
    {
      path: "/feedback",
      name: "Feedback",
      component: () => import("@/views/FeedbackView.vue"),
      meta: { title: "反馈" },
    },
    {
      path: "/my",
      name: "My",
      component: () => import("@/views/MyView.vue"),
      meta: { title: "我的" },
    },
    {
      path: "/admin",
      redirect: "/admin/users",
    },
    {
      path: "/admin/ai-settings",
      name: "AdminAISettings",
      component: () => import("@/views/AdminAISettings.vue"),
      meta: { title: "AI 设置" },
    },
    {
      path: "/admin/users",
      name: "AdminUsers",
      component: () => import("@/views/AdminUsers.vue"),
      meta: { title: "用户管理" },
    },
    {
      path: "/admin/system-settings",
      name: "AdminSystemSettings",
      component: () => import("@/views/AdminSystemSettings.vue"),
      meta: { title: "系统设置" },
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
    return "/today";
  }

  return true;
});

export default router;
