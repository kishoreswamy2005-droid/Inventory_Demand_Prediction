import axios, { AxiosError, AxiosInstance } from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface ApiErrorBody {
  detail?: string;
  errors?: { field: string; message: string }[];
}

/** Normalise any backend error into a human-readable message. */
export function errorMessage(err: unknown): string {
  const axiosErr = err as AxiosError<ApiErrorBody>;
  if (axiosErr?.response?.data) {
    const data = axiosErr.response.data;
    // Field-level validation errors are the most specific message.
    if (data.errors?.length) {
      return data.errors.map((e) => `${e.field}: ${e.message}`).join("; ");
    }
    if (typeof data.detail === "string") return data.detail;
    if (data.detail) return JSON.stringify(data.detail);
  }
  if (axiosErr?.message === "Network Error") {
    return "Cannot reach the API server. Is the backend running?";
  }
  return axiosErr?.message ?? "Unexpected error";
}

export default api;
