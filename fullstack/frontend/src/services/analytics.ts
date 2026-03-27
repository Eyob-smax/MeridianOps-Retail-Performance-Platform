import { apiClient } from "@/services/api";

export interface DashboardSummary {
  id: number;
  name: string;
  description: string | null;
  widget_count: number;
  allowed_store_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface DashboardWidget {
  id: string;
  kind: "kpi" | "trend" | "breakdown" | "table";
  title: string;
  metric: "revenue" | "orders" | "refunds" | "gross_margin";
  dimension: "store" | "date" | null;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DashboardDetail {
  id: number;
  name: string;
  description: string | null;
  widgets: DashboardWidget[];
  allowed_store_ids: number[];
  default_start_date: string | null;
  default_end_date: string | null;
  store_options: Array<{ id: number; name: string }>;
  read_only: boolean;
  data: {
    filters: { store_ids: number[]; start_date: string; end_date: string };
    totals: {
      orders: number;
      revenue: string;
      refunds: string;
      cost: string;
      gross_margin: string;
    };
  };
}

export async function listDashboards() {
  const { data } = await apiClient.get<DashboardSummary[]>("/analytics/dashboards");
  return data;
}

export async function createDashboard(payload: {
  name: string;
  description?: string;
  widgets: DashboardWidget[];
  allowed_store_ids: number[];
  default_start_date?: string;
  default_end_date?: string;
}) {
  const { data } = await apiClient.post<DashboardDetail>("/analytics/dashboards", payload);
  return data;
}

export async function getDashboard(dashboardId: number) {
  const { data } = await apiClient.get<DashboardDetail>(`/analytics/dashboards/${dashboardId}`);
  return data;
}

export async function exportDashboardMetadata(dashboardId: number, format: "csv" | "png" | "pdf") {
  const { data } = await apiClient.get<{
    filename: string;
    content_type: string;
    size_bytes: number;
  }>(`/analytics/dashboards/${dashboardId}/export/metadata`, { params: { format } });
  return data;
}

export async function createDashboardShareLink(
  dashboardId: number,
  payload: { start_date?: string; end_date?: string; allowed_store_ids?: number[] } = {},
) {
  const { data } = await apiClient.post(
    `/analytics/dashboards/${dashboardId}/share-links`,
    payload,
  );
  return data as {
    id: number;
    dashboard_id: number;
    token: string;
    share_url: string;
    readonly: boolean;
    is_active: boolean;
  };
}
