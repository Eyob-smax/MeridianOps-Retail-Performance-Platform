<template>
  <section>
    <h1>Campaign Detail</h1>
    <p>Inspect configured campaign constraints and active lifecycle settings.</p>

    <section class="panel">
      <div class="form-grid">
        <input v-model.number="campaignId" type="number" min="1" placeholder="Campaign ID" />
      </div>
      <button class="btn" @click="loadDetail">Load</button>
    </section>

    <section class="panel" v-if="campaign">
      <h2>{{ campaign.name }}</h2>
      <p>ID: {{ campaign.id }}</p>
      <p>Type: {{ campaign.campaign_type }}</p>
      <p>Window: {{ campaign.effective_start }} to {{ campaign.effective_end }}</p>
      <p>Daily cap: {{ campaign.daily_redemption_cap }}</p>
      <p>Per-member daily limit: {{ campaign.per_member_daily_limit }}</p>
      <p>Active: {{ campaign.is_active ? "yes" : "no" }}</p>
      <p>Percent off: {{ campaign.percent_off ?? "-" }}</p>
      <p>Fixed amount off: {{ campaign.fixed_amount_off ?? "-" }}</p>
      <p>Threshold amount: {{ campaign.threshold_amount ?? "-" }}</p>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import axios from "axios";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getCampaign, type CampaignRecord } from "@/services/campaigns";

const route = useRoute();
const campaignId = ref(Number(route.params.id || 1));
const campaign = ref<CampaignRecord | null>(null);
const errorMessage = ref("");

async function loadDetail() {
  try {
    errorMessage.value = "";
    campaign.value = await getCampaign(Number(campaignId.value));
  } catch (error) {
    errorMessage.value = extractError(error);
    campaign.value = null;
  }
}

function extractError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? "Request failed.");
  }
  return "Request failed.";
}

onMounted(async () => {
  await loadDetail();
});
</script>
