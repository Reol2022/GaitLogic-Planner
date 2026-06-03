import request from "./request";
import type { WorkoutLog, WorkoutLogPayload } from "@/types/models";

export function getWorkoutLog(plannedWorkoutId: number) {
  return request.get<WorkoutLog>(`/api/workout-logs/${plannedWorkoutId}`);
}

export function updateWorkoutLog(plannedWorkoutId: number, payload: WorkoutLogPayload) {
  return request.put<WorkoutLog>(`/api/workout-logs/${plannedWorkoutId}`, payload);
}

