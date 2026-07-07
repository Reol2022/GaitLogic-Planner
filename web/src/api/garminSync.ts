import request from "./request";
import type {
  ExternalActivityRead,
  ExternalSyncJobRead,
  GarminActivityReconcilePayload,
  GarminActivityReconcileSummary,
  GarminConnectPayload,
  GarminConnectResponse,
  GarminConnectionStatus,
  GarminSyncPayload,
} from "@/types/models";

export function getGarminStatus(skipErrorMessage = false) {
  return request.get<GarminConnectionStatus>("/integrations/garmin/status", { skipErrorMessage });
}

export function connectGarmin(payload: GarminConnectPayload) {
  return request.post<GarminConnectResponse>("/integrations/garmin/connect", payload);
}

export function disconnectGarmin() {
  return request.post<GarminConnectionStatus>("/integrations/garmin/disconnect");
}

export function updateGarminSyncSettings(payload: { auto_import_enabled: boolean }) {
  return request.put<GarminConnectionStatus>("/integrations/garmin/settings", payload);
}

export function startGarminSync(payload: GarminSyncPayload, idempotencyKey?: string) {
  return request.post<ExternalSyncJobRead>("/integrations/garmin/sync", payload, {
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

export function listGarminSyncJobs() {
  return request.get<ExternalSyncJobRead[]>("/integrations/garmin/sync-jobs");
}

export function retryGarminSyncJob(jobId: number) {
  return request.post<ExternalSyncJobRead>(`/integrations/garmin/sync-jobs/${jobId}/retry`);
}

export function listGarminActivities() {
  return request.get<ExternalActivityRead[]>("/integrations/garmin/activities");
}

export function resolveGarminActivity(activityId: number, payload: { action: string; planned_workout_id?: number | null; reason?: string | null }) {
  return request.post<ExternalActivityRead>(`/integrations/garmin/activities/${activityId}/resolve`, payload);
}

export function reconcileGarminActivities(payload: GarminActivityReconcilePayload) {
  return request.post<GarminActivityReconcileSummary>("/integrations/garmin/activities/reconcile", payload);
}
