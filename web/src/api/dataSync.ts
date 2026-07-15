import request from "./request";
import type {
  DataSyncConnectionRead,
  DataSyncSummary,
  ExternalSyncJobRead,
  GarminSyncPayload,
  ProviderListResponse,
} from "@/types/models";

export function listDataSyncProviders(skipErrorMessage = false) {
  return request.get<ProviderListResponse>("/data-sync/providers", { skipErrorMessage });
}

export function listDataSyncConnections(skipErrorMessage = false) {
  return request.get<DataSyncConnectionRead[]>("/data-sync/connections", { skipErrorMessage });
}

export function getDataSyncConnection(providerKey: string, skipErrorMessage = false) {
  return request.get<DataSyncConnectionRead>(`/data-sync/connections/${providerKey}`, { skipErrorMessage });
}

export function getDataSyncSummary(skipErrorMessage = false) {
  return request.get<DataSyncSummary>("/data-sync/summary", { skipErrorMessage });
}

export function updateDataSyncPreferences(
  providerKey: string,
  payload: { auto_import_enabled?: boolean; auto_sync_enabled?: boolean },
) {
  return request.patch<DataSyncConnectionRead>(`/data-sync/connections/${providerKey}/preferences`, payload);
}

export function startDataSync(providerKey: string, payload: GarminSyncPayload, idempotencyKey?: string) {
  return request.post<ExternalSyncJobRead>(`/data-sync/connections/${providerKey}/sync`, payload, {
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}
