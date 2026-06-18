import request from "./request";
import type { SystemSettings } from "@/types/models";
import { cacheSystemSettings } from "@/utils/systemSettingsCache";

export async function getSystemSettings() {
  const settings = await request.get<SystemSettings>("/system-settings", { skipErrorMessage: true });
  cacheSystemSettings(settings);
  return settings;
}
