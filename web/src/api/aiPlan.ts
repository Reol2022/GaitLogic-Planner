import request from "./request";
import type {
  AIPlanDraft,
  AIPlanExportFormat,
  AIPlanGeneratePayload,
  AIPlanGenerateResult,
  AIPlanQuota,
} from "@/types/models";

export function generateAIPlan(payload: AIPlanGeneratePayload) {
  return request.post<AIPlanGenerateResult>("/ai-plan/generate", payload, {
    timeout: 600000,
    skipErrorMessage: true,
  });
}

export function getAIPlanDrafts() {
  return request.get<AIPlanDraft[]>("/ai-plan/drafts");
}

export function getAIPlanDraftDetail(id: number) {
  return request.get<AIPlanDraft>(`/ai-plan/drafts/${id}`);
}

export function applyAIPlanDraft(id: number) {
  return request.post<{ message: string; cycle_id: number }>(`/ai-plan/drafts/${id}/apply`);
}

export function rejectAIPlanDraft(id: number) {
  return request.post<{ message: string }>(`/ai-plan/drafts/${id}/reject`);
}

export function exportAIPlanDraft(id: number, format: AIPlanExportFormat) {
  return request.get<Blob>(`/ai-plan/drafts/${id}/export`, {
    params: { format },
    responseType: "blob",
  });
}

export function getAIPlanQuota() {
  return request.get<AIPlanQuota>("/ai-plan/quota");
}
