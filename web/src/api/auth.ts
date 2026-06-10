import request from "./request";
import type {
  TokenResponse,
  UserAccount,
  UserLoginPayload,
  UserRegisterPayload,
} from "@/types/models";

export const TOKEN_STORAGE_KEY = "gaitlogic_access_token";

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function registerUser(payload: UserRegisterPayload) {
  return request.post<UserAccount>("/auth/register", payload);
}

export function loginUser(payload: UserLoginPayload) {
  return request.post<TokenResponse>("/auth/login", payload);
}

export function getCurrentUser() {
  return request.get<UserAccount>("/auth/me");
}

export function logoutUser() {
  return request.post<{ message: string }>("/auth/logout");
}
