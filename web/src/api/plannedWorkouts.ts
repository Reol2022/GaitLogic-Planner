import request from "./request";
import type {
  PlannedWorkout,
  PlannedWorkoutPayload,
  WorkoutMainTypeNormalized,
} from "@/types/models";

export interface WorkoutFilters {
  cycle_id?: number | null;
  block_id?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  main_type_normalized?: WorkoutMainTypeNormalized | null;
}

export function listPlannedWorkouts(filters: WorkoutFilters = {}) {
  return request.get<PlannedWorkout[]>("/planned-workouts", { params: filters });
}

export function createPlannedWorkout(payload: PlannedWorkoutPayload) {
  return request.post<PlannedWorkout>("/planned-workouts", payload);
}

export function updatePlannedWorkout(id: number, payload: Partial<PlannedWorkoutPayload>) {
  return request.put<PlannedWorkout>(`/planned-workouts/${id}`, payload);
}

export function deletePlannedWorkout(id: number) {
  return request.delete(`/planned-workouts/${id}`);
}

export function listTodayWorkouts(date: string) {
  return request.get<PlannedWorkout[]>("/today", { params: { date } });
}
