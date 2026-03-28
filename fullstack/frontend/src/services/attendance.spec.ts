import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

import { apiClient } from "@/services/api";
import {
  attendanceCheckIn,
  attendanceCheckOut,
  getAttendanceRules,
  rotateAttendanceQr,
  updateAttendanceRules,
} from "@/services/attendance";

describe("attendance service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and updates rules", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        tolerance_minutes: 5,
        auto_break_after_hours: 6,
        auto_break_minutes: 30,
        cross_day_shift_cutoff_hour: 6,
        late_early_penalty_hours: "0.25",
      },
    });
    const rules = await getAttendanceRules();
    expect(rules.tolerance_minutes).toBe(5);

    vi.mocked(apiClient.patch).mockResolvedValue({ data: { ...rules, tolerance_minutes: 7 } });
    const updated = await updateAttendanceRules({ ...rules, tolerance_minutes: 7 });
    expect(apiClient.patch).toHaveBeenCalledWith("/attendance/rules", {
      ...rules,
      tolerance_minutes: 7,
    });
    expect(updated.tolerance_minutes).toBe(7);
  });

  it("rotates qr and submits checkin checkout", async () => {
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({ data: { token: "qr_abc", expires_at: "2026-03-27T10:00:00Z" } })
      .mockResolvedValueOnce({
        data: {
          id: 1,
          user_id: 1,
          check_in_at: "2026-03-27T09:00:00Z",
          check_out_at: null,
          status: "open",
          scheduled_start_at: null,
          scheduled_end_at: null,
        },
      })
      .mockResolvedValueOnce({
        data: {
          shift: {
            id: 1,
            user_id: 1,
            check_in_at: "2026-03-27T09:00:00Z",
            check_out_at: "2026-03-27T17:00:00Z",
            status: "closed",
            scheduled_start_at: null,
            scheduled_end_at: null,
          },
          daily_result: {
            id: 2,
            user_id: 1,
            business_date: "2026-03-27",
            worked_hours: "7.50",
            auto_break_minutes: 30,
            late_incidents: 0,
            early_incidents: 0,
            penalty_hours: "0.00",
          },
        },
      });

    const qr = await rotateAttendanceQr();
    expect(qr.token).toBe("qr_abc");

    const checkIn = await attendanceCheckIn({ device_id: "DEV-1", qr_token: "qr_abc" });
    expect(checkIn.status).toBe("open");

    const checkOut = await attendanceCheckOut({ device_id: "DEV-1", qr_token: "qr_abc" });
    expect(checkOut.daily_result.worked_hours).toBe("7.50");
  });

  it("submits nfc checkin checkout", async () => {
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({
        data: {
          id: 10,
          user_id: 1,
          check_in_at: "2026-03-27T09:00:00Z",
          check_out_at: null,
          status: "open",
          scheduled_start_at: null,
          scheduled_end_at: null,
        },
      })
      .mockResolvedValueOnce({
        data: {
          shift: {
            id: 10,
            user_id: 1,
            check_in_at: "2026-03-27T09:00:00Z",
            check_out_at: "2026-03-27T12:00:00Z",
            status: "closed",
            scheduled_start_at: null,
            scheduled_end_at: null,
          },
          daily_result: {
            id: 20,
            user_id: 1,
            business_date: "2026-03-27",
            worked_hours: "3.00",
            auto_break_minutes: 0,
            late_incidents: 0,
            early_incidents: 0,
            penalty_hours: "0.00",
          },
        },
      });

    const checkIn = await attendanceCheckIn({ device_id: "DEV-2", nfc_tag: "NFC-1" });
    expect(checkIn.status).toBe("open");
    expect(apiClient.post).toHaveBeenCalledWith("/attendance/check-in", {
      device_id: "DEV-2",
      nfc_tag: "NFC-1",
    });

    const checkOut = await attendanceCheckOut({ device_id: "DEV-2", nfc_tag: "NFC-1" });
    expect(checkOut.shift.status).toBe("closed");
    expect(apiClient.post).toHaveBeenCalledWith("/attendance/check-out", {
      device_id: "DEV-2",
      nfc_tag: "NFC-1",
    });
  });
});
