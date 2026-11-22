import request from './request';

export interface SyncJobSnapshot {
  job_id: number;
  scope: string;
  status: string;
  outcome: string;
  started_at: string | null;
  finished_at: string | null;
  requested_start: string | null;
  requested_end: string | null;
  fetched_count: number;
  created_count: number;
  updated_count: number;
  failed_count: number;
  needs_review_count: number;
  committed: boolean;
  error_category: string | null;
}

export interface SyncFreshness {
  status: string;
  sync_status?: string;
  data_freshness?: 'FRESH' | 'STALE' | 'UNKNOWN';
  data_freshness_by_scope?: Record<string, 'FRESH' | 'STALE' | 'UNKNOWN'>;
  scope: string;
  enabled: boolean;
  interval_minutes: number;
  recovery_enabled: boolean;
  job_id: number | null;
  last_job?: SyncJobSnapshot | null;
  last_job_by_scope?: Record<string, SyncJobSnapshot | null>;
  blocking_job?: SyncJobSnapshot | null;
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
