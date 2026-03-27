import { apiClient } from "@/services/api";

export interface InventoryPosition {
  sku: string;
  item_name: string;
  location_code: string;
  on_hand_qty: string;
  reserved_qty: string;
  available_qty: string;
}

export interface InventoryLedgerEntry {
  id: number;
  sku: string;
  location_code: string;
  entry_type: string;
  quantity_delta: string;
  reservation_delta: string;
  order_reference: string | null;
}

export async function createInventoryItem(payload: {
  sku: string;
  name: string;
  unit?: string;
  batch_tracking_enabled?: boolean;
  expiry_tracking_enabled?: boolean;
}) {
  const { data } = await apiClient.post("/inventory/items", payload);
  return data;
}

export async function createInventoryLocation(payload: { code: string; name: string }) {
  const { data } = await apiClient.post("/inventory/locations", payload);
  return data;
}

export async function postReceiving(payload: {
  location_code: string;
  note?: string;
  lines: Array<{ sku: string; quantity: string; batch_no?: string; expiry_date?: string }>;
}) {
  const { data } = await apiClient.post("/inventory/receiving", payload);
  return data;
}

export async function postTransfer(payload: {
  source_location_code: string;
  target_location_code: string;
  note?: string;
  lines: Array<{ sku: string; quantity: string; batch_no?: string; expiry_date?: string }>;
}) {
  const { data } = await apiClient.post("/inventory/transfers", payload);
  return data;
}

export async function postCount(payload: {
  location_code: string;
  note?: string;
  lines: Array<{ sku: string; counted_qty: string; batch_no?: string; expiry_date?: string }>;
}) {
  const { data } = await apiClient.post("/inventory/counts", payload);
  return data;
}

export async function createReservation(payload: {
  order_reference: string;
  sku: string;
  location_code: string;
  quantity: string;
}) {
  const { data } = await apiClient.post("/inventory/reservations", payload);
  return data;
}

export async function releaseReservation(reservationId: number) {
  const { data } = await apiClient.post("/inventory/reservations/release", {
    reservation_id: reservationId,
  });
  return data;
}

export async function listPositions(params?: { sku?: string; location_code?: string }) {
  const { data } = await apiClient.get<InventoryPosition[]>("/inventory/positions", { params });
  return data;
}

export async function listInventoryLedger(limit = 100) {
  const { data } = await apiClient.get<InventoryLedgerEntry[]>("/inventory/ledger", {
    params: { limit },
  });
  return data;
}
