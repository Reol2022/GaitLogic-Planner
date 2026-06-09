import request from "./request";
import type { AIPlanDraft, AIPlanGeneratePayload, AIPlanGenerateResult, AIPlanQuota } from "@/types/models";

export function generateAIPlan(payload: AIPlanGeneratePayload) {
  return request.post<AIPlanGenerateResult>("/api/ai-plan/generate", payload);
}

export function getAIPlanDrafts() {
  return request.get<AIPlanDraft[]>("/api/ai-plan/drafts");
}

export function getAIPlanDraftDetail(id: number) {
  return request.get<AIPlanDraft>(`/api/ai-plan/drafts/${id}`);
}

export function applyAIPlanDraft(id: number) {
  return request.post<{ message: string; cycle_id: number }>(`/api/ai-plan/drafts/${id}/apply`);
}

export function rejectAIPlanDraft(id: number) {
  return request.post<{ message: string }>(`/api/ai-plan/drafts/${id}/reject`);
}

export function getAIPlanQuota() {
  return request.get<AIPlanQuota>("/api/ai-plan/quota");
}
