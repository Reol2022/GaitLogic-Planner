import axios from "axios";
import type { AxiosError, AxiosRequestConfig } from "axios";
import { ElMessage } from "element-plus";
import { requestAuth } from "@/utils/authPrompt";
import { getCachedAuthEntryMode } from "@/utils/systemSettingsCache";

const TOKEN_STORAGE_KEY = "gaitlogic_access_token";

interface AppRequestConfig extends AxiosRequestConfig {
  skipErrorMessage?: boolean;
}

interface ErrorResponseBody {
  code?: string | number;
  message?: string;
  detail?: unknown;
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 120000,
});

export function getRequestErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : "请求处理失败，请稍后重试。";
  }

  const axiosError = error as AxiosError<ErrorResponseBody>;
  const serverMessage = axiosError.response?.data?.message;
  if (serverMessage) {
    return serverMessage;
  }

  if (axiosError.code === "ECONNABORTED") {
    return "请求超时，服务器处理时间较长，请稍后重试。";
  }

  if (axiosError.code === "ERR_NETWORK" || !axiosError.response) {
    return "网络错误，无法连接服务器，请检查网络或后端服务状态。";
  }

  const status = axiosError.response.status;
  if (status === 403) return "没有权限执行当前操作。";
  if (status === 404) return "请求的接口不存在或功能暂未开放。";
  if (status === 500) return "服务器处理请求时发生异常，请稍后重试。";
  if (status === 503) return "服务暂时不可用，请稍后重试。";
  return axiosError.message || "后端请求失败，请稍后重试。";
}

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<ErrorResponseBody>) => {
    const config = error?.config as AppRequestConfig | undefined;
    if (error?.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
        if (getCachedAuthEntryMode() === "modal") {
          requestAuth(window.location.pathname + window.location.search);
        } else {
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
        }
      }
      return Promise.reject(error);
    }

    if (!config?.skipErrorMessage) {
      ElMessage.error(getRequestErrorMessage(error));
    }
    return Promise.reject(error);
  },
);

const request = {
  get<T>(url: string, config?: AppRequestConfig) {
    return client.get<T, T>(url, config);
  },
  post<T>(url: string, data?: unknown, config?: AppRequestConfig) {
    return client.post<T, T>(url, data, config);
  },
  put<T>(url: string, data?: unknown, config?: AppRequestConfig) {
    return client.put<T, T>(url, data, config);
  },
  patch<T>(url: string, data?: unknown, config?: AppRequestConfig) {
    return client.patch<T, T>(url, data, config);
  },
  delete<T = unknown>(url: string, config?: AppRequestConfig) {
    return client.delete<T, T>(url, config);
  },
};

export default request;
