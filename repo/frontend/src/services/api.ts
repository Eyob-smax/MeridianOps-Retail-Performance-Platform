import axios from "axios";

import { useUiStore } from "@/stores/ui";
import { sanitizePayload } from "@/utils/sanitize";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 8000,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const ui = useUiStore();
  ui.beginRequest();

  if (config.data !== undefined) {
    config.data = sanitizePayload(config.data);
  }
  if (config.params !== undefined) {
    config.params = sanitizePayload(config.params) as Record<string, unknown>;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    const ui = useUiStore();
    ui.endRequest();
    return response;
  },
  (error) => {
    const ui = useUiStore();
    ui.endRequest();
    return Promise.reject(error);
  },
);
