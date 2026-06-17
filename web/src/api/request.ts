import axios from "axios";
import type { AxiosRequestConfig } from "axios";
import { ElMessage } from "element-plus";

const TOKEN_STORAGE_KEY = "gaitlogic_access_token";

interface AppRequestConfig extends AxiosRequestConfig {
  skipErrorMessage?: boolean;
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 120000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const config = error?.config as AppRequestConfig | undefined;
    if (error?.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      }
      return Promise.reject(error);
    }

    if (!config?.skipErrorMessage) {
      const message =
        error?.code === "ECONNABORTED"
          ? "请求处理时间较长，请稍后刷新查看结果"
          : error?.response?.data?.message || error?.message || "后端请求失败，请检查服务状态";
      ElMessage.error(message);
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
  delete<T = unknown>(url: string, config?: AppRequestConfig) {
    return client.delete<T, T>(url, config);
  },
};

export default request;
