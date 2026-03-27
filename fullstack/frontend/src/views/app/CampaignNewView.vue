<template>
  <section>
    <h1>Create Campaign</h1>
    <p>Define campaign type, active window, and redemption constraints.</p>

    <section class="panel">
      <div class="form-grid">
        <input v-model="name" placeholder="Campaign name" />
        <select v-model="campaignType">
          <option value="percent_off">percent_off</option>
          <option value="fixed_amount">fixed_amount</option>
          <option value="full_reduction">full_reduction</option>
        </select>
        <input v-model="effectiveStart" type="date" />
        <input v-model="effectiveEnd" type="date" />
        <input v-model.number="dailyCap" type="number" min="1" placeholder="Daily cap" />
        <input
          v-model.number="memberDailyLimit"
          type="number"
          min="1"
          placeholder="Per-member limit"
        />
        <input v-model="percentOff" placeholder="Percent off" />
        <input v-model="fixedAmount" placeholder="Fixed amount off" />
        <input v-model="thresholdAmount" placeholder="Threshold amount" />
      </div>
      <button class="btn" @click="onCreate">Create</button>
    </section>

    <p v-if="createdCampaignId">Created campaign ID: {{ createdCampaignId }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref } from "vue";

import { createCampaign } from "@/services/campaigns";

const name = ref("Weekend Offer");
const campaignType = ref<"percent_off" | "fixed_amount" | "full_reduction">("percent_off");
const effectiveStart = ref("2026-01-01");
const effectiveEnd = ref("2027-12-31");
const dailyCap = ref(200);
const memberDailyLimit = ref(1);
const percentOff = ref("0.10");
const fixedAmount = ref("10.00");
const thresholdAmount = ref("50.00");
const createdCampaignId = ref<number | null>(null);
const errorMessage = ref("");

async function onCreate() {
  try {
    errorMessage.value = "";
    const created = await createCampaign({
      name: name.value,
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
    createdCampaignId.value = created.id;
  } catch (error) {
    errorMessage.value = extractError(error);
  }
}

function extractError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? "Request failed.");
  }
  return "Request failed.";
}
</script>
