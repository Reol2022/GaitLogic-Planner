import request from "./request";
import type { TrainingBlock, TrainingBlockPayload } from "@/types/models";

export function listTrainingBlocks(cycleId?: number | null) {
  return request.get<TrainingBlock[]>("/training-blocks", {
    params: { cycle_id: cycleId || undefined },
  });
}

export function createTrainingBlock(payload: TrainingBlockPayload) {
  return request.post<TrainingBlock>("/training-blocks", payload);
}

export function updateTrainingBlock(id: number, payload: Partial<TrainingBlockPayload>) {
  return request.put<TrainingBlock>(`/training-blocks/${id}`, payload);
}

export function deleteTrainingBlock(id: number) {
  return request.delete(`/training-blocks/${id}`);
}
