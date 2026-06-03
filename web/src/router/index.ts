import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
  ],
});

export default router;

