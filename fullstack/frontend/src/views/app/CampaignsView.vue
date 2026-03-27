<template>
  <section>
    <h1>Campaigns</h1>
    <p>Campaign setup, coupon issuance, and redemption terminal.</p>

    <section class="panel">
      <h2>Create Campaign</h2>
      <div class="form-grid">
        <input v-model="campaignName" placeholder="Campaign name" />
        <select v-model="campaignType">
          <option value="percent_off">percent_off</option>
          <option value="fixed_amount">fixed_amount</option>
          <option value="full_reduction">full_reduction</option>
        </select>
        <input v-model="effectiveStart" type="date" />
        <input v-model="effectiveEnd" type="date" />
        <input v-model="dailyCap" type="number" min="1" placeholder="Daily cap" />
        <input v-model="memberDailyLimit" type="number" min="1" placeholder="Per-member limit" />
        <input v-model="percentOff" placeholder="Percent off (e.g. 0.10)" />
        <input v-model="fixedAmount" placeholder="Fixed amount off" />
        <input v-model="thresholdAmount" placeholder="Threshold amount" />
      </div>
      <button class="btn" @click="onCreateCampaign">Create Campaign</button>
    </section>

    <section class="panel">
      <h2>Campaign List</h2>
      <button class="btn" @click="loadCampaigns">Refresh</button>
      <table class="data-table" v-if="campaigns.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Type</th>
            <th>Active Window</th>
            <th>Daily Cap</th>
            <th>Per Member</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="campaign in campaigns" :key="campaign.id">
            <td>{{ campaign.id }}</td>
            <td>{{ campaign.name }}</td>
            <td>{{ campaign.campaign_type }}</td>
            <td>{{ campaign.effective_start }} to {{ campaign.effective_end }}</td>
            <td>{{ campaign.daily_redemption_cap }}</td>
            <td>{{ campaign.per_member_daily_limit }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Issue Coupon</h2>
      <div class="form-grid">
        <input v-model="issueCampaignId" type="number" placeholder="Campaign ID" />
        <select v-model="issueMethod">
          <option value="account_assignment">account_assignment</option>
          <option value="printable_qr">printable_qr</option>
        </select>
        <input v-model="issueMemberCode" placeholder="Member code (optional for QR)" />
      </div>
      <button class="btn" @click="onIssueCoupon">Issue</button>
      <p v-if="lastIssue">
        Issued {{ lastIssue.coupon_code }}
        {{ lastIssue.qr_payload ? `(QR: ${lastIssue.qr_payload})` : "" }}
      </p>
    </section>

    <section class="panel">
      <h2>Redeem Coupon</h2>
      <div class="form-grid">
        <input v-model="redeemCouponCode" placeholder="Coupon code" />
        <input v-model="redeemMemberCode" placeholder="Member code (if required)" />
        <input v-model="redeemPreTaxAmount" placeholder="Pre-tax amount" />
        <input v-model="redeemOrderReference" placeholder="Order reference" />
      </div>
      <button class="btn" @click="onRedeemCoupon">Redeem</button>
      <p v-if="lastRedemption" :class="lastRedemption.success ? 'ok' : 'error'">
        {{ lastRedemption.reason_code }} - {{ lastRedemption.message }} | discount
        {{ lastRedemption.discount_amount }} | final {{ lastRedemption.final_amount }}
      </p>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  createCampaign,
  issueCoupon,
  listCampaigns,
  redeemCoupon,
  type CampaignRecord,
  type CouponIssueResponse,
  type CouponRedeemResponse,
} from "@/services/campaigns";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const campaigns = ref<CampaignRecord[]>([]);
const errorMessage = ref("");

const campaignName = ref("Promo 10% Off");
const campaignType = ref<"percent_off" | "fixed_amount" | "full_reduction">("percent_off");
const effectiveStart = ref("2026-01-01");
const effectiveEnd = ref("2027-12-31");
const dailyCap = ref(200);
const memberDailyLimit = ref(1);
const percentOff = ref("0.10");
const fixedAmount = ref("10.00");
const thresholdAmount = ref("50.00");

const issueCampaignId = ref(1);
const issueMethod = ref<"account_assignment" | "printable_qr">("printable_qr");
const issueMemberCode = ref("");
const lastIssue = ref<CouponIssueResponse | null>(null);

const redeemCouponCode = ref("");
const redeemMemberCode = ref("");
const redeemPreTaxAmount = ref("100.00");
const redeemOrderReference = ref("ORDER-001");
const lastRedemption = ref<CouponRedeemResponse | null>(null);

async function loadCampaigns() {
  try {
    errorMessage.value = "";
    campaigns.value = await listCampaigns();
    if (campaigns.value.length > 0) {
      issueCampaignId.value = campaigns.value[0].id;
    }
  } catch (error) {
    errorMessage.value = extractError(error);
  }
}

async function onCreateCampaign() {
  try {
    errorMessage.value = "";
    await createCampaign({
      name: campaignName.value,
      campaign_type: campaignType.value,
      effective_start: effectiveStart.value,
      effective_end: effectiveEnd.value,
      daily_redemption_cap: Number(dailyCap.value),
      per_member_daily_limit: Number(memberDailyLimit.value),
      percent_off: campaignType.value === "percent_off" ? percentOff.value : undefined,
      fixed_amount_off:
        campaignType.value === "fixed_amount" || campaignType.value === "full_reduction"
          ? fixedAmount.value
          : undefined,
      threshold_amount: campaignType.value === "full_reduction" ? thresholdAmount.value : undefined,
    });
    await loadCampaigns();
    ui.success("Created", "Campaign created and campaign list updated.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Campaign creation failed.");
  }
}

async function onIssueCoupon() {
  try {
    errorMessage.value = "";
    lastIssue.value = await issueCoupon({
      campaign_id: Number(issueCampaignId.value),
      issuance_method: issueMethod.value,
      member_code: issueMemberCode.value || undefined,
    });
    redeemCouponCode.value = lastIssue.value.coupon_code;
    ui.success("Posted", `Coupon ${lastIssue.value.coupon_code} issued successfully.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Coupon issuance failed.");
  }
}

async function onRedeemCoupon() {
  try {
    errorMessage.value = "";
    lastRedemption.value = await redeemCoupon({
      coupon_code: redeemCouponCode.value,
      member_code: redeemMemberCode.value || undefined,
      pre_tax_amount: redeemPreTaxAmount.value,
      order_reference: redeemOrderReference.value,
    });
    if (lastRedemption.value.success) {
      ui.success("Posted", `Redemption successful (${lastRedemption.value.reason_code}).`);
    } else {
      ui.info("Posted", `${lastRedemption.value.reason_code}: ${lastRedemption.value.message}`);
    }
  } catch (error) {
    errorMessage.value = notifyError(error, "Coupon redemption failed.");
  }
}

onMounted(async () => {
  await loadCampaigns();
});
</script>
