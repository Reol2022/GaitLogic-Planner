import axios from "axios";
import type { AxiosRequestConfig } from "axios";
import { ElMessage } from "element-plus";

const TOKEN_STORAGE_KEY = "gaitlogic_access_token";

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
    if (error?.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      }
    }

    const message =
      error?.response?.data?.message || error?.message || "后端请求失败，请检查服务状态";
    ElMessage.error(message);
    return Promise.reject(error);
  },
);

const request = {
  get<T>(url: string, config?: AxiosRequestConfig) {
    return client.get<T, T>(url, config);
  },
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return client.post<T, T>(url, data, config);
  },
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return client.put<T, T>(url, data, config);
  },
  delete<T = unknown>(url: string, config?: AxiosRequestConfig) {
    return client.delete<T, T>(url, config);
  },
};

export default request;
