import type { UserRole } from "@/types/roles";

import { apiClient } from "@/services/api";

export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  roles: UserRole[];
}

export interface LoginPayload {
  username: string;
  password: string;
}

interface LoginResponse {
  message: string;
  user: AuthUser;
}

interface SessionResponse {
  authenticated: boolean;
  user: AuthUser | null;
}

export interface SecurityPolicy {
  min_password_length: number;
  max_failed_attempts: number;
  lockout_minutes: number;
  session_minutes: number;
  masking_enabled_default: boolean;
  encryption_enabled: boolean;
}

export async function login(payload: LoginPayload): Promise<AuthUser> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login", payload);
  return data.user;
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
}

export async function fetchSession(): Promise<AuthUser | null> {
  try {
    const { data } = await apiClient.get<SessionResponse>("/auth/session");
    return data.authenticated ? data.user : null;
  } catch {
    return null;
  }
}

export async function fetchSecurityPolicy(): Promise<SecurityPolicy> {
  const { data } = await apiClient.get<SecurityPolicy>("/auth/security-policy");
  return data;
}
