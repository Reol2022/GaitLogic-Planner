import request from "./request";
import type {
  PaceCalculationPayload,
  PaceCalculationResult,
  PaceProfile,
  PaceProfileCreatePayload,
} from "@/types/models";

export function calculatePaces(payload: PaceCalculationPayload) {
  return request.post<PaceCalculationResult>("/api/pace-calculator/calculate", payload);
}

export function createPaceProfile(payload: PaceProfileCreatePayload) {
  return request.post<PaceProfile>("/api/pace-profiles", payload);
}

export function listPaceProfiles() {
  return request.get<PaceProfile[]>("/api/pace-profiles");
}

export function getPaceProfile(id: number) {
  return request.get<PaceProfile>(`/api/pace-profiles/${id}`);
}

export function deletePaceProfile(id: number) {
  return request.delete(`/api/pace-profiles/${id}`);
}

export function applyPaceProfileToRules(id: number) {
  return request.post<{ message: string; updated_count: number }>(
    `/api/pace-profiles/${id}/apply-to-pace-rules`,
  );
}
