import request from "./request";
import type {
  WorkoutImportApplyResponse,
  WorkoutImportBatchRead,
  WorkoutImportCreateResponse,
  WorkoutImportItemRead,
  WorkoutImportStructuredPayload,
} from "@/types/models";

export function downloadWorkoutImportTemplate() {
  return request.get<Blob>("/workout-imports/template", { responseType: "blob" });
}

export function createStructuredWorkoutImport(payload: WorkoutImportStructuredPayload, idempotencyKey?: string) {
  return request.post<WorkoutImportCreateResponse>("/workout-imports/structured", payload, {
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

export function uploadWorkoutImportFile(
  file: File,
  payload: Pick<WorkoutImportStructuredPayload, "merge_strategy" | "timezone" | "client_request_id">,
  idempotencyKey?: string,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("merge_strategy", payload.merge_strategy);
  formData.append("timezone", payload.timezone || "Asia/Shanghai");
  if (payload.client_request_id) formData.append("client_request_id", payload.client_request_id);
  return request.post<WorkoutImportCreateResponse>("/workout-imports/file", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    },
  });
}

export function listWorkoutImports() {
  return request.get<WorkoutImportBatchRead[]>("/workout-imports");
}

export function getWorkoutImport(batchId: number) {
  return request.get<WorkoutImportBatchRead>(`/workout-imports/${batchId}`);
}

export function updateWorkoutImportItem(batchId: number, itemId: number, payload: Partial<WorkoutImportItemRead>) {
  return request.patch<WorkoutImportBatchRead>(`/workout-imports/${batchId}/items/${itemId}`, payload);
}

export function validateWorkoutImport(batchId: number) {
  return request.post<WorkoutImportBatchRead>(`/workout-imports/${batchId}/validate`);
}

export function applyWorkoutImport(batchId: number) {
  return request.post<WorkoutImportApplyResponse>(`/workout-imports/${batchId}/apply`);
}

export function cancelWorkoutImport(batchId: number) {
  return request.post<WorkoutImportBatchRead>(`/workout-imports/${batchId}/cancel`);
}
