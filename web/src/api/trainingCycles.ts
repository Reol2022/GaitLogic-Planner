import request from "./request";
import type { TrainingCycle, TrainingCyclePayload } from "@/types/models";

export function listTrainingCycles() {
  return request.get<TrainingCycle[]>("/api/training-cycles");
}

export function createTrainingCycle(payload: TrainingCyclePayload) {
  return request.post<TrainingCycle>("/api/training-cycles", payload);
}

export function updateTrainingCycle(id: number, payload: Partial<TrainingCyclePayload>) {
  return request.put<TrainingCycle>(`/api/training-cycles/${id}`, payload);
}

export function deleteTrainingCycle(id: number) {
  return request.delete(`/api/training-cycles/${id}`);
}

