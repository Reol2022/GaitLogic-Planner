import request from "./request";
import type {
  PlanImportDraftRead,
  PlanImportStructuredPayload,
  PlanImportWorkoutItem,
} from "@/types/models";

export const PLAN_IMPORT_TEMPLATE_FILENAME = "plan-import-template.xlsx";

export function downloadPlanImportTemplate() {
  return request.get<Blob>("/plan-imports/template", {
    responseType: "blob",
  });
}

export function createStructuredPlanImport(payload: PlanImportStructuredPayload, idempotencyKey?: string) {
  return request.post<PlanImportDraftRead>("/plan-imports/structured", payload, {
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

export function uploadPlanImportFile(file: File, payload: Omit<PlanImportStructuredPayload, "workouts">) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source", payload.source || "file");
  formData.append("anchor_strategy", payload.anchor_strategy);
  formData.append("merge_strategy", payload.merge_strategy);
  formData.append("timezone", payload.timezone || "Asia/Shanghai");
  if (payload.client_request_id) formData.append("client_request_id", payload.client_request_id);
  if (payload.effective_date) formData.append("effective_date", payload.effective_date);
  if (payload.target_cycle_id) formData.append("target_cycle_id", String(payload.target_cycle_id));
  if (payload.target_block_id) formData.append("target_block_id", String(payload.target_block_id));

  return request.post<PlanImportDraftRead>("/plan-imports/file", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}

export function getPlanImport(importId: number) {
  return request.get<PlanImportDraftRead>(`/plan-imports/${importId}`);
}

export function updatePlanImportItem(importId: number, itemId: number, normalizedItem: PlanImportWorkoutItem) {
  return request.patch<PlanImportDraftRead>(`/plan-imports/${importId}/items/${itemId}`, normalizedItem);
}

export function validatePlanImport(importId: number) {
  return request.post<PlanImportDraftRead>(`/plan-imports/${importId}/validate`);
}

export function applyPlanImport(importId: number) {
  return request.post<{ import_id: number; status: string; diff_summary: unknown }>(`/plan-imports/${importId}/apply`);
}

export function cancelPlanImport(importId: number) {
  return request.post<{ import_id: number; status: string }>(`/plan-imports/${importId}/cancel`);
}
