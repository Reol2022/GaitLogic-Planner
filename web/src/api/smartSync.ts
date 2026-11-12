import request from './request';

export interface SyncFreshness {
  status: string;
  scope: string;
  enabled: boolean;
  interval_minutes: number;
  recovery_enabled: boolean;
  job_id: number | null;
  error_category: string | null;
  last_success_at: string | null;
  last_success_by_scope: Record<string, string | null>;
  next_retry_at: string | null;
}
export function getSmartSync() {
  return request.get<SyncFreshness>('/integrations/garmin/smart-sync', { skipErrorMessage: true });
}
export function checkSmartSync() {
  return request.post<SyncFreshness>('/integrations/garmin/smart-sync/check', { trigger: 'home' }, { skipErrorMessage: true });
}
export function saveSmartSync(payload: { enabled: boolean; interval_minutes: number; recovery_enabled: boolean }) {
  return request.put<SyncFreshness>('/integrations/garmin/smart-sync', payload);
}
