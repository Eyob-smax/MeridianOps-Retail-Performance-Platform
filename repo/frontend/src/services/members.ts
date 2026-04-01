import { apiClient } from "@/services/api";

export interface MemberRecord {
  id: number;
  member_code: string;
  full_name: string;
  tier: "base" | "silver" | "gold";
  stored_value_enabled: boolean;
  points_balance: number;
  wallet_balance: string | null;
}

export interface PointsLedgerEntry {
  id: number;
  member_id: number;
  points_delta: number;
  reason: string;
  pre_tax_amount: string | null;
}

export interface WalletLedgerEntry {
  id: number;
  member_id: number;
  entry_type: "credit" | "debit";
  amount: string;
  balance_after: string;
  reason: string;
}

export async function searchMembers(search?: string): Promise<MemberRecord[]> {
  const { data } = await apiClient.get<MemberRecord[]>("/members", {
    params: search ? { search } : undefined,
  });
  return data;
}

export async function getMember(memberCode: string): Promise<MemberRecord> {
  const { data } = await apiClient.get<MemberRecord>(`/members/${memberCode}`);
  return data;
}

export async function accruePoints(memberCode: string, preTaxAmount: string, reason: string): Promise<MemberRecord> {
  const { data } = await apiClient.post<MemberRecord>(`/members/${memberCode}/points/accrue`, {
    pre_tax_amount: preTaxAmount,
    reason,
  });
  return data;
}

export async function creditWallet(memberCode: string, amount: string, reason: string): Promise<MemberRecord> {
  const { data } = await apiClient.post<MemberRecord>(`/members/${memberCode}/wallet/credit`, {
    amount,
    reason,
  });
  return data;
}

export async function debitWallet(memberCode: string, amount: string, reason: string): Promise<MemberRecord> {
  const { data } = await apiClient.post<MemberRecord>(`/members/${memberCode}/wallet/debit`, {
    amount,
    reason,
  });
  return data;
}

export async function fetchPointsLedger(memberCode: string): Promise<PointsLedgerEntry[]> {
  const { data } = await apiClient.get<PointsLedgerEntry[]>(`/members/${memberCode}/points-ledger`);
  return data;
}

export async function fetchWalletLedger(memberCode: string): Promise<WalletLedgerEntry[]> {
  const { data } = await apiClient.get<WalletLedgerEntry[]>(`/members/${memberCode}/wallet-ledger`);
  return data;
}
