import { createRouter, createWebHistory } from "vue-router";
import { getStoredToken } from "@/api/auth";
import { getOnboardingStatus } from "@/api/onboarding";
import { getSystemSettings } from "@/api/systemSettings";
import { requestAuth } from "@/utils/authPrompt";
import { getCachedAuthEntryMode } from "@/utils/systemSettingsCache";

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
      path: "/welcome",
      name: "Welcome",
      component: () => import("@/views/WelcomeView.vue"),
      meta: { title: "开始训练计划" },
    },
    {
      path: "/dashboard",
      name: "Dashboard",
      component: () => import("@/views/DashboardView.vue"),
      meta: { title: "训练统计" },
    },
    {
      path: "/training-readiness",
      name: "TrainingReadiness",
      component: () => import("@/views/TrainingReadinessView.vue"),
      meta: { title: "负荷与恢复" },
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
      path: "/todos",
      name: "TaskCenter",
      component: () => import("@/views/TaskCenterView.vue"),
      meta: { title: "待办中心" },
    },
    {
      path: "/training-plan",
      name: "TrainingPlanCenter",
      component: () => import("@/views/TrainingPlanCenterView.vue"),
      meta: { title: "训练计划" },
    },
    {
      path: "/data-management",
      name: "DataManagement",
      component: () => import("@/views/DataManagementView.vue"),
      meta: { title: "数据管理" },
    },
    {
      path: "/weekly-review",
      name: "WeeklyReview",
      component: () => import("@/views/WeeklyReviewView.vue"),
      meta: { title: "智能周复盘" },
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
      redirect: "/plan-imports",
    },
    {
      path: "/my-training-plan",
      redirect: "/training-plan",
    },
    {
      path: "/plan-import",
      redirect: "/training-plan?tab=import",
    },
    {
      path: "/plan-imports",
      name: "PlanImport",
      component: () => import("@/views/PlanImportView.vue"),
      meta: { title: "课表导入" },
    },
    {
      path: "/workout-import",
      name: "WorkoutImport",
      component: () => import("@/views/WorkoutImportView.vue"),
      meta: { title: "训练记录导入" },
    },
    {
      path: "/garmin-sync",
      redirect: "/data-sync/garmin",
    },
    {
      path: "/data-sync",
      name: "DataSync",
      component: () => import("@/views/DataSyncView.vue"),
      meta: { title: "数据同步" },
    },
    {
      path: "/data-sync/garmin",
      name: "GarminSync",
      component: () => import("@/views/GarminSyncView.vue"),
      meta: { title: "Garmin 同步" },
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
    {
      path: "/admin/rule-governance",
      name: "AdminRuleGovernance",
      component: () => import("@/views/AdminRuleGovernance.vue"),
      meta: { title: "科学规则治理" },
    },
    {
      path: "/404",
      name: "NotFound",
      component: () => import("@/views/NotFoundView.vue"),
      meta: { title: "页面不存在", public: true },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/404",
      meta: { public: true },
    },
  ],
});

router.beforeEach(async (to) => {
  const token = getStoredToken();
  let authEntryMode = getCachedAuthEntryMode();
  try {
    const settings = await getSystemSettings();
    authEntryMode = settings.auth_entry_mode;
  } catch {
    authEntryMode = getCachedAuthEntryMode();
  }

  if (!to.meta.public && !token) {
    if (authEntryMode === "modal") {
      setTimeout(() => requestAuth(to.fullPath), 0);
      return true;
    }
    return {
      path: "/login",
      query: { redirect: to.fullPath },
    };
  }

  if ((to.name === "Login" || to.name === "Register") && token) {
    return "/today";
  }

  if ((to.name === "Login" || to.name === "Register") && !token && authEntryMode === "modal") {
    setTimeout(() => requestAuth(String(to.query.redirect || "/today")), 0);
    return "/today";
  }

  if (token && to.name !== "Welcome" && !to.meta.public && !localStorage.getItem("gaitlogic_welcome_skipped")) {
    try {
      const status = await getOnboardingStatus();
      if (status.should_show_welcome) return "/welcome";
    } catch {
      return true;
    }
  }

  return true;
});

export default router;
