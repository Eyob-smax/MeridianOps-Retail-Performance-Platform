<template>
  <section>
    <h1>Checkout</h1>
    <p>Scan coupon and apply redemption with explicit eligibility feedback.</p>

    <div class="panel">
      <label>Coupon code</label>
      <input v-model="couponCode" placeholder="CPN-XXXXXXXXXXXX" />
      <label>Member code (optional)</label>
      <input v-model="memberCode" placeholder="MEM-001" />
      <label>Pre-tax amount</label>
      <input v-model="preTaxAmount" placeholder="100.00" />
      <label>Order reference</label>
      <input v-model="orderReference" placeholder="POS-ORDER-001" />
      <button class="btn" @click="onRedeem">Redeem</button>
    </div>

    <div v-if="result" class="panel">
      <h2>Redemption Result</h2>
      <p :class="result.success ? 'ok' : 'error'">
        {{ result.reason_code }} - {{ result.message }}
      </p>
      <p>Discount: {{ result.discount_amount }}</p>
      <p>Final amount: {{ result.final_amount }}</p>
      <p>Campaign ID: {{ result.campaign_id ?? "N/A" }}</p>
    </div>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref } from "vue";

import { redeemCoupon, type CouponRedeemResponse } from "@/services/campaigns";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();

const couponCode = ref("");
const memberCode = ref("");
const preTaxAmount = ref("100.00");
const orderReference = ref("POS-ORDER-001");
const result = ref<CouponRedeemResponse | null>(null);
const errorMessage = ref("");

async function onRedeem() {
  try {
    errorMessage.value = "";
    result.value = await redeemCoupon({
      coupon_code: couponCode.value,
      member_code: memberCode.value || undefined,
      pre_tax_amount: preTaxAmount.value,
      order_reference: orderReference.value,
    });
    if (result.value.success) {
      ui.success("Posted", "Checkout redemption posted successfully.");
    } else {
      ui.info("Posted", `${result.value.reason_code}: ${result.value.message}`);
    }
  } catch (error) {
    if (axios.isAxiosError(error)) {
      errorMessage.value = String(error.response?.data?.detail ?? "Redemption failed");
      ui.error("Action Failed", errorMessage.value);
      return;
    }
    errorMessage.value = "Redemption failed";
    ui.error("Action Failed", errorMessage.value);
  }
}
</script>
