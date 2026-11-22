import { api } from './api';
import type { SystemSettings, SystemSettingsPayload } from '@/types/models';

export async function getConsoleSystemSettings(): Promise<SystemSettings> {
  return (await api.get<SystemSettings>('/admin/system-settings')).data;
}

export async function saveConsoleSystemSettings(settings: SystemSettingsPayload): Promise<SystemSettings> {
  // Only these two existing system-wide settings are writable here.
  return (await api.put<SystemSettings>('/admin/system-settings', {
    auth_entry_mode: settings.auth_entry_mode,
    allow_public_registration: settings.allow_public_registration,
  })).data;
}
