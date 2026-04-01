import { describe, expect, it } from "vitest";

import { navigationItems } from "@/app/navigation";

describe("navigation visibility", () => {
  it("includes health route for all roles", () => {
    const health = navigationItems.find((item) => item.path === "/app/system/health");
    expect(health).toBeDefined();
    expect(health?.roles.length).toBe(5);
  });

  it("keeps security route administrator-only", () => {
    const security = navigationItems.find((item) => item.path === "/app/admin/security");
    expect(security?.roles).toEqual(["administrator"]);
  });
});
