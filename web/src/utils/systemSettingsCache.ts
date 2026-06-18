import type { AuthEntryMode, SystemSettings } from "@/types/models";

const AUTH_ENTRY_MODE_KEY = "gaitlogic_auth_entry_mode";
const ALLOW_PUBLIC_REGISTRATION_KEY = "gaitlogic_allow_public_registration";

export function getCachedAuthEntryMode(): AuthEntryMode {
  const value = localStorage.getItem(AUTH_ENTRY_MODE_KEY);
  return value === "modal" ? "modal" : "standalone";
}

export function getCachedAllowPublicRegistration() {
  return localStorage.getItem(ALLOW_PUBLIC_REGISTRATION_KEY) !== "false";
}

export function cacheSystemSettings(settings: SystemSettings) {
  localStorage.setItem(AUTH_ENTRY_MODE_KEY, settings.auth_entry_mode);
  localStorage.setItem(ALLOW_PUBLIC_REGISTRATION_KEY, String(settings.allow_public_registration));
}
