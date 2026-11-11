import axios from "axios";
import request, { getRequestErrorMessage } from "./request";
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

export function loginUser(payload: UserLoginPayload, config?: { skipErrorMessage?: boolean }) {
  return request.post<TokenResponse>("/auth/login", payload, config);
}

export function getLoginErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) return "用户名或密码错误，请重新输入。";
    if (error.response?.status === 429) return "登录尝试过于频繁，请稍后再试。";
  }
  return getRequestErrorMessage(error);
}

export function getCurrentUser() {
  return request.get<UserAccount>("/auth/me");
}

export function logoutUser() {
  return request.post<{ message: string }>("/auth/logout");
}
