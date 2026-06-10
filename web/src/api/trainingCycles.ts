import request from "./request";
import type { TrainingCycle, TrainingCyclePayload } from "@/types/models";

export function listTrainingCycles() {
  return request.get<TrainingCycle[]>("/training-cycles");
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
