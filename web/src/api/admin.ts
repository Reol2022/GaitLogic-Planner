import request from "./request";
import type { AdminAISettings, AdminAISettingsPayload } from "@/types/models";

export function getAdminAISettings() {
  return request.get<AdminAISettings>("/admin/ai-settings");
}

export function updateAdminAISettings(payload: AdminAISettingsPayload) {
  return request.put<AdminAISettings>("/admin/ai-settings", payload);
}
