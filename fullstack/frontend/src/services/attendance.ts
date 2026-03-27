import { apiClient } from "@/services/api";

export interface AttendanceRule {
  tolerance_minutes: number;
  auto_break_after_hours: number;
  auto_break_minutes: number;
  late_early_penalty_hours: string;
}

export interface AttendanceShiftRow {
  id: number;
  user_id: number;
  check_in_at: string;
  check_out_at: string | null;
  status: string;
  scheduled_start_at: string | null;
  scheduled_end_at: string | null;
}

export interface AttendanceMakeupRow {
  id: number;
  user_id: number;
  business_date: string;
  reason: string;
  status: string;
  manager_note: string | null;
  manager_user_id: number | null;
  created_at: string;
  reviewed_at: string | null;
}

export async function getAttendanceRules() {
  const { data } = await apiClient.get<AttendanceRule>("/attendance/rules");
  return data;
}

export async function updateAttendanceRules(payload: AttendanceRule) {
  const { data } = await apiClient.patch<AttendanceRule>("/attendance/rules", payload);
  return data;
}

export async function rotateAttendanceQr() {
  const { data } = await apiClient.post<{ token: string; expires_at: string }>(
    "/attendance/qr/rotate",
  );
  return data;
}

export async function attendanceCheckIn(payload: {
  device_id: string;
  qr_token: string;
  check_in_at?: string;
  scheduled_start_at?: string;
  scheduled_end_at?: string;
  latitude?: string;
  longitude?: string;
}) {
  const { data } = await apiClient.post<AttendanceShiftRow>("/attendance/check-in", payload);
  return data;
}

export async function attendanceCheckOut(payload: {
  device_id: string;
  qr_token: string;
  check_out_at?: string;
  latitude?: string;
  longitude?: string;
}) {
  const { data } = await apiClient.post<{
    shift: AttendanceShiftRow;
    daily_result: {
      id: number;
      user_id: number;
      business_date: string;
      worked_hours: string;
      auto_break_minutes: number;
      late_incidents: number;
      early_incidents: number;
      penalty_hours: string;
    };
  }>("/attendance/check-out", payload);
  return data;
}

export async function listMyShifts(limit = 30) {
  const { data } = await apiClient.get<AttendanceShiftRow[]>("/attendance/me/shifts", {
    params: { limit },
  });
  return data;
}

export async function createMakeupRequest(payload: { business_date: string; reason: string }) {
  const { data } = await apiClient.post<AttendanceMakeupRow>(
    "/attendance/makeup-requests",
    payload,
  );
  return data;
}

export async function listMakeupRequests() {
  const { data } = await apiClient.get<AttendanceMakeupRow[]>("/attendance/makeup-requests");
  return data;
}

export async function approveMakeupRequest(requestId: number, managerNote: string) {
  const { data } = await apiClient.post<AttendanceMakeupRow>(
    `/attendance/makeup-requests/${requestId}/approve`,
    { manager_note: managerNote },
  );
  return data;
}

export async function exportPayrollCsv(startDate: string, endDate: string) {
  const { data } = await apiClient.get<string>("/attendance/payroll-export", {
    params: { start_date: startDate, end_date: endDate },
    responseType: "text" as never,
  });
  return data;
}
