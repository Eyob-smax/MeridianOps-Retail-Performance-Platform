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
  filters?: Array<{
    key: string;
    operator: "eq" | "in" | "gte" | "lte" | "between";
    value: string;
  }>;
  links?: Array<{
    source_filter_key: string;
    target_filter_key: string;
  }>;
}

export interface DashboardData {
  filters: { store_ids: number[]; start_date: string; end_date: string };
  totals: {
    orders: number;
    revenue: string;
    refunds: string;
    cost: string;
    gross_margin: string;
  };
  by_store?: Array<{
    store_id: number;
    store_name: string;
    orders: number;
    revenue: string;
    refunds: string;
    cost: string;
    gross_margin: string;
  }>;
  by_date?: Array<{
    business_date: string;
    orders: number;
    revenue: string;
    refunds: string;
    cost: string;
    gross_margin: string;
  }>;
  rows?: Array<{
    store_id: number;
    store_name: string;
    business_date: string;
    orders: number;
    revenue: string;
    refunds: string;
    cost: string;
    gross_margin: string;
  }>;
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
  data: DashboardData;
}

export interface SharedDashboardDetail {
  dashboard_id: number;
  token: string;
  name: string;
  description: string | null;
  widgets: DashboardWidget[];
  allowed_store_ids: number[];
  store_options: Array<{ id: number; name: string }>;
  read_only: boolean;
  data: DashboardData;
  created_at: string;
  updated_at: string;
}

export interface StoreDrillDown {
  dashboard_id: number;
  store_id: number;
  store_name: string;
  start_date: string;
  end_date: string;
  orders: number;
  revenue: string;
  refunds: string;
  cost: string;
  gross_margin: string;
}

export interface DateDrillDown {
  dashboard_id: number;
  business_date: string;
  start_date: string;
  end_date: string;
  orders: number;
  revenue: string;
  refunds: string;
  cost: string;
  gross_margin: string;
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

export async function getSharedDashboard(token: string) {
  const { data } = await apiClient.get<SharedDashboardDetail>(`/analytics/shared/${token}`);
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

function _filenameFromDisposition(
  contentDisposition: string | undefined,
  fallback: string,
): string {
  if (!contentDisposition) {
    return fallback;
  }
  const match = contentDisposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? fallback;
}

export async function exportDashboardFile(dashboardId: number, format: "csv" | "png" | "pdf") {
  const response = await apiClient.get<Blob>(`/analytics/dashboards/${dashboardId}/export`, {
    params: { format },
    responseType: "blob",
  });
  const fallbackName = `dashboard-${dashboardId}.${format}`;
  const filename = _filenameFromDisposition(response.headers["content-disposition"], fallbackName);
  return {
    blob: response.data,
    filename,
  };
}

export async function getDashboardStoreDrilldown(dashboardId: number, storeId: number) {
  const { data } = await apiClient.get<StoreDrillDown>(
    `/analytics/dashboards/${dashboardId}/drilldown/store/${storeId}`,
  );
  return data;
}

export async function getDashboardDateDrilldown(dashboardId: number, businessDate: string) {
  const { data } = await apiClient.get<DateDrillDown>(
    `/analytics/dashboards/${dashboardId}/drilldown/date/${businessDate}`,
  );
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
