import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from "@/services/api";
import {
  createDashboard,
  createDashboardShareLink,
  exportDashboardMetadata,
  getDashboard,
  listDashboards,
} from "@/services/analytics";

describe("analytics service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists dashboards and fetches detail", async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({
        data: [
          {
            id: 1,
            name: "Ops",
            description: null,
            widget_count: 2,
            allowed_store_ids: [101],
            created_at: "",
            updated_at: "",
          },
        ],
      })
      .mockResolvedValueOnce({
        data: {
          id: 1,
          name: "Ops",
          description: null,
          widgets: [],
          allowed_store_ids: [101],
          default_start_date: null,
          default_end_date: null,
          store_options: [],
          read_only: false,
          data: {
            filters: { store_ids: [101], start_date: "2026-03-20", end_date: "2026-03-27" },
            totals: {
              orders: 10,
              revenue: "100.00",
              refunds: "0.00",
              cost: "50.00",
              gross_margin: "50.00",
            },
          },
        },
      });

    const rows = await listDashboards();
    const detail = await getDashboard(1);

    expect(rows).toHaveLength(1);
    expect(detail.id).toBe(1);
  });

  it("creates dashboard and share link and fetches export metadata", async () => {
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({
        data: {
          id: 9,
          name: "Regional",
          description: null,
          widgets: [],
          allowed_store_ids: [101],
          default_start_date: null,
          default_end_date: null,
          store_options: [],
          read_only: false,
          data: {
            filters: { store_ids: [101], start_date: "2026-03-20", end_date: "2026-03-27" },
            totals: {
              orders: 0,
              revenue: "0.00",
              refunds: "0.00",
              cost: "0.00",
              gross_margin: "0.00",
            },
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          id: 1,
          dashboard_id: 9,
          token: "abc",
          share_url: "http://localhost:5173/shared/abc",
          readonly: true,
          is_active: true,
        },
      });
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { filename: "regional.csv", content_type: "text/csv", size_bytes: 1234 },
    });

    const dashboard = await createDashboard({
      name: "Regional",
      widgets: [
        {
          id: "w",
          kind: "kpi",
          title: "Revenue",
          metric: "revenue",
          dimension: null,
          x: 0,
          y: 0,
          w: 4,
          h: 2,
        },
      ],
      allowed_store_ids: [101],
    });
    const share = await createDashboardShareLink(dashboard.id);
    const metadata = await exportDashboardMetadata(dashboard.id, "csv");

    expect(share.dashboard_id).toBe(9);
    expect(metadata.content_type).toBe("text/csv");
  });
});
