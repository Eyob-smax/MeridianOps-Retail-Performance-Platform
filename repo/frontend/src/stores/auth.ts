import { defineStore } from "pinia";

import { fetchSession, login, logout, type AuthUser } from "@/services/auth";
import type { UserRole } from "@/types/roles";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  initialized: boolean;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    user: null,
    loading: false,
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user),
    role: (state): UserRole | null => state.user?.roles[0] ?? null,
    roles: (state): UserRole[] => state.user?.roles ?? [],
    username: (state): string => state.user?.username ?? "",
    displayName: (state): string => state.user?.display_name ?? "",
  },
  actions: {
    async initialize() {
      if (this.initialized) return;
      this.loading = true;
      this.user = await fetchSession();
      this.loading = false;
      this.initialized = true;
    },
    async signIn(username: string, password: string) {
      this.loading = true;
      try {
        this.user = await login({ username, password });
        this.initialized = true;
      } finally {
        this.loading = false;
      }
    },
    async signOut() {
      this.loading = true;
      await logout();
      this.user = null;
      this.loading = false;
      this.initialized = true;
    },
  },
});
