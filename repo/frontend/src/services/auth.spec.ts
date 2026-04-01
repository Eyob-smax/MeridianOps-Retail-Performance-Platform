import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from "@/services/api";
import { fetchSession, login } from "@/services/auth";

describe("auth service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns user on login with store context", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        message: "Login successful",
        user: {
          id: 7,
          store_id: 101,
          username: "manager",
          display_name: "Store Manager",
          roles: ["store_manager"],
        },
      },
    });

    const user = await login({ username: "manager", password: "ChangeMeNow123" });

    expect(user.store_id).toBe(101);
    expect(user.roles).toContain("store_manager");
  });

  it("returns null session when unauthenticated", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { authenticated: false, user: null },
    });

    const session = await fetchSession();

    expect(session).toBeNull();
  });
});
