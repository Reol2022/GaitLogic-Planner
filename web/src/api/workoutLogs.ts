import request from "./request";
import type { WorkoutCompletionContext, WorkoutLog, WorkoutLogPayload } from "@/types/models";

export function getWorkoutLog(plannedWorkoutId: number) {
  return request.get<WorkoutLog>(`/workout-logs/${plannedWorkoutId}`);
}

export function updateWorkoutLog(plannedWorkoutId: number, payload: WorkoutLogPayload) {
  return request.put<WorkoutLog>(`/workout-logs/${plannedWorkoutId}`, payload);
}

export function getWorkoutCompletionContext(plannedWorkoutId: number) {
  return request.get<WorkoutCompletionContext>(`/planned-workouts/${plannedWorkoutId}/completion-context`);
}
