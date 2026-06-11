import request from "./request";
import type {
  AdminAISettings,
  AdminAISettingsPayload,
  AdminUser,
  AdminUserUpdatePayload,
} from "@/types/models";

export function getAdminAISettings() {
  return request.get<AdminAISettings>("/admin/ai-settings");
}

export function updateAdminAISettings(payload: AdminAISettingsPayload) {
  return request.put<AdminAISettings>("/admin/ai-settings", payload);
}

export function listAdminUsers(keyword?: string) {
  return request.get<AdminUser[]>("/admin/users", { params: { keyword: keyword || undefined } });
}

export function updateAdminUser(id: number, payload: AdminUserUpdatePayload) {
  return request.put<AdminUser>(`/admin/users/${id}`, payload);
}
