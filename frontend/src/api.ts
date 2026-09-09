import axios, { AxiosError } from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) localStorage.removeItem("token");
    const message = error.response?.data?.detail || error.message || "خطای ارتباط با سرور";
    return Promise.reject(new Error(message));
  },
);

export const api = {
  async get<T>(path: string): Promise<T> {
    const response = await apiClient.get<T>(path);
    return response.data;
  },
  async post<T>(path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
    const response = await apiClient.post<T>(path, body, idempotencyKey ? { headers: { "Idempotency-Key": idempotencyKey } } : undefined);
    return response.data;
  },
  async put<T>(path: string, body?: unknown): Promise<T> {
    const response = await apiClient.put<T>(path, body);
    return response.data;
  },
  async delete<T>(path: string): Promise<T> {
    const response = await apiClient.delete<T>(path);
    return response.data;
  },
};
