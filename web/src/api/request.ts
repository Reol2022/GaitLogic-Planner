import axios from "axios";
import type { AxiosRequestConfig } from "axios";
import { ElMessage } from "element-plus";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 12000,
});

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
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
