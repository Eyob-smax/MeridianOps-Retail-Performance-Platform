import { defineStore } from "pinia";

export type ToastType = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  type: ToastType;
  title: string;
  message: string;
}

interface UiState {
  pendingRequests: number;
  toasts: ToastItem[];
  nextToastId: number;
}

export const useUiStore = defineStore("ui", {
  state: (): UiState => ({
    pendingRequests: 0,
    toasts: [],
    nextToastId: 1,
  }),
  getters: {
    isLoading: (state) => state.pendingRequests > 0,
  },
  actions: {
    beginRequest() {
      this.pendingRequests += 1;
    },
    endRequest() {
      this.pendingRequests = Math.max(0, this.pendingRequests - 1);
    },
    pushToast(type: ToastType, title: string, message: string, ttlMs = 3500) {
      const toast: ToastItem = {
        id: this.nextToastId,
        type,
        title,
        message,
      };
      this.nextToastId += 1;
      this.toasts.push(toast);
      window.setTimeout(() => {
        this.removeToast(toast.id);
      }, ttlMs);
    },
    removeToast(id: number) {
      this.toasts = this.toasts.filter((item) => item.id !== id);
    },
    success(title: string, message: string) {
      this.pushToast("success", title, message);
    },
    error(title: string, message: string) {
      this.pushToast("error", title, message, 5000);
    },
    info(title: string, message: string) {
      this.pushToast("info", title, message);
    },
  },
});
