<template>
  <section>
    <h1>Inventory Transfers</h1>
    <p>Move stock between locations with availability checks and append-only ledger entries.</p>

    <section class="panel">
      <h2>Post Transfer</h2>
      <div class="form-grid">
        <input v-model="sourceLocationCode" placeholder="Source location" />
        <input v-model="targetLocationCode" placeholder="Target location" />
        <input v-model="sku" placeholder="SKU" />
        <input v-model="quantity" placeholder="Quantity" />
      </div>
      <button class="btn" @click="onTransfer">Post Transfer</button>
    </section>

    <section class="panel">
      <h2>Recent Ledger</h2>
      <button class="btn" @click="refreshLedger">Refresh</button>
      <table class="data-table" v-if="ledger.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>SKU</th>
            <th>Location</th>
            <th>Qty Delta</th>
            <th>Reserved Delta</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in ledger" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.entry_type }}</td>
            <td>{{ row.sku }}</td>
            <td>{{ row.location_code }}</td>
            <td>{{ row.quantity_delta }}</td>
            <td>{{ row.reservation_delta }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="message">{{ message }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listInventoryLedger, postTransfer, type InventoryLedgerEntry } from "@/services/inventory";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const sourceLocationCode = ref("MAIN");
const targetLocationCode = ref("BACK");
const sku = ref("SKU-100");
const quantity = ref("2.000");

const ledger = ref<InventoryLedgerEntry[]>([]);
const message = ref("");
const errorMessage = ref("");

async function onTransfer() {
  try {
    message.value = "";
    errorMessage.value = "";
    await postTransfer({
      source_location_code: sourceLocationCode.value,
      target_location_code: targetLocationCode.value,
      lines: [{ sku: sku.value, quantity: quantity.value }],
    });
    await refreshLedger();
    message.value = "Transfer posted.";
    ui.success("Posted", "Transfer posted and ledger refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Transfer posting failed.");
  }
}

async function refreshLedger() {
  ledger.value = await listInventoryLedger(100);
}

onMounted(async () => {
  try {
    await refreshLedger();
  } catch {
    // Best-effort initial fetch.
  }
});
</script>
