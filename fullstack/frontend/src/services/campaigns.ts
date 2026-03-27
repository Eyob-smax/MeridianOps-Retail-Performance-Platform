import { apiClient } from "@/services/api";

export type CampaignType = "percent_off" | "fixed_amount" | "full_reduction";

export interface CampaignRecord {
  id: number;
  name: string;
  campaign_type: CampaignType;
  effective_start: string;
  effective_end: string;
  daily_redemption_cap: number;
  per_member_daily_limit: number;
  is_active: boolean;
  percent_off: string | null;
  fixed_amount_off: string | null;
  threshold_amount: string | null;
}

export interface CreateCampaignPayload {
  name: string;
  campaign_type: CampaignType;
  effective_start: string;
  effective_end: string;
  daily_redemption_cap: number;
  per_member_daily_limit: number;
  percent_off?: string;
  fixed_amount_off?: string;
  threshold_amount?: string;
}

export interface CouponIssueResponse {
  coupon_code: string;
  campaign_id: number;
  issuance_method: "account_assignment" | "printable_qr";
  qr_payload: string | null;
}

export interface CouponRedeemResponse {
  success: boolean;
  reason_code: string;
  message: string;
  discount_amount: string;
  final_amount: string;
  campaign_id: number | null;
}

export async function listCampaigns(): Promise<CampaignRecord[]> {
  const { data } = await apiClient.get<CampaignRecord[]>("/campaigns");
  return data;
}

export async function createCampaign(payload: CreateCampaignPayload): Promise<CampaignRecord> {
  const { data } = await apiClient.post<CampaignRecord>("/campaigns", payload);
  return data;
}

export async function getCampaign(campaignId: number): Promise<CampaignRecord> {
  const { data } = await apiClient.get<CampaignRecord>(`/campaigns/${campaignId}`);
  return data;
}

export async function issueCoupon(payload: {
  campaign_id: number;
  issuance_method: "account_assignment" | "printable_qr";
  member_code?: string;
}): Promise<CouponIssueResponse> {
  const { data } = await apiClient.post<CouponIssueResponse>("/campaigns/issue", payload);
  return data;
}

export async function redeemCoupon(payload: {
  coupon_code: string;
  member_code?: string;
  pre_tax_amount: string;
  order_reference: string;
}): Promise<CouponRedeemResponse> {
  const { data } = await apiClient.post<CouponRedeemResponse>("/campaigns/redeem", payload);
  return data;
}
