import request from "./request";
import type {
  RecoveryQuickPayload,
  RecoveryQuickRead,
  TaskListResponse,
  TodayDashboard,
  TrainingPlanOverview,
} from "@/types/models";

export function getTodayDashboard(skipErrorMessage = false) {
  return request.get<TodayDashboard>("/dashboard/today", { skipErrorMessage });
}

export function getTodos(limit?: number, skipErrorMessage = false) {
  return request.get<TaskListResponse>("/todos", {
    params: { limit },
    skipErrorMessage,
  });
}

export function completeTodo(taskKey: string) {
  return request.patch<TaskListResponse>(`/todos/${encodeURIComponent(taskKey)}`, { status: "done" });
}

export function getTrainingPlanOverview(skipErrorMessage = false) {
  return request.get<TrainingPlanOverview>("/training-plan/overview", { skipErrorMessage });
}

export function getQuickRecovery(skipErrorMessage = false) {
  return request.get<RecoveryQuickRead>("/recovery-checkins/quick", { skipErrorMessage });
}

export function saveQuickRecovery(payload: RecoveryQuickPayload) {
  return request.put<RecoveryQuickRead>("/recovery-checkins/quick", payload);
}
