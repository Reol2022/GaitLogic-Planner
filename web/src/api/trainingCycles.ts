import request from "./request";
import type { TrainingCycle, TrainingCyclePayload } from "@/types/models";

export function listTrainingCycles() {
  return request.get<TrainingCycle[]>("/training-cycles");
}

export function getActiveTrainingCycle() {
  return request.get<TrainingCycle>("/training-cycles/active", { skipErrorMessage: true });
}

export function createTrainingCycle(payload: TrainingCyclePayload) {
  return request.post<TrainingCycle>("/training-cycles", payload);
}

export function updateTrainingCycle(id: number, payload: Partial<TrainingCyclePayload>) {
  return request.put<TrainingCycle>(`/training-cycles/${id}`, payload);
}

export function deleteTrainingCycle(id: number) {
  return request.delete(`/training-cycles/${id}`);
}

export function activateTrainingCycle(id: number, effectiveStartDate: string) {
  return request.post<TrainingCycle>(`/training-cycles/${id}/activate`, {
    effective_start_date: effectiveStartDate,
    complete_current_cycle: true,
  });
}

export function completeTrainingCycle(id: number, actualEndDate?: string | null) {
  return request.post<TrainingCycle>(`/training-cycles/${id}/complete`, {
    actual_end_date: actualEndDate ?? null,
  });
}

export function archiveTrainingCycle(id: number) {
  return request.post<TrainingCycle>(`/training-cycles/${id}/archive`);
}
