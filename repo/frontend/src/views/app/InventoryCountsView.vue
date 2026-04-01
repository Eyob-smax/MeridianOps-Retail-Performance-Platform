<template>
  <section>
    <h1>Inventory Counts</h1>
    <p>Post cycle counts and variances; available and reserved stock stay visible in real time.</p>

    <section class="panel">
      <h2>Post Count</h2>
      <div class="form-grid">
        <input v-model="locationCode" placeholder="Location code" />
        <input v-model="sku" placeholder="SKU" />
        <input v-model="countedQty" placeholder="Counted quantity" />
      </div>
      <button class="btn" @click="onPostCount">Post Count</button>
    </section>

    <section class="panel">
      <h2>Position Snapshot</h2>
      <button class="btn" @click="refreshPositions">Refresh</button>
      <table class="data-table" v-if="positions.length > 0">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Item</th>
            <th>Location</th>
            <th>On Hand</th>
            <th>Reserved</th>
            <th>Available</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in positions" :key="`${row.sku}-${row.location_code}`">
            <td>{{ row.sku }}</td>
            <td>{{ row.item_name }}</td>
            <td>{{ row.location_code }}</td>
            <td>{{ row.on_hand_qty }}</td>
            <td>{{ row.reserved_qty }}</td>
            <td>{{ row.available_qty }}</td>
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

import { listPositions, postCount, type InventoryPosition } from "@/services/inventory";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const locationCode = ref("MAIN");
const sku = ref("SKU-100");
const countedQty = ref("8.000");

const positions = ref<InventoryPosition[]>([]);
const message = ref("");
const errorMessage = ref("");

async function onPostCount() {
  try {
    message.value = "";
    errorMessage.value = "";
    await postCount({
      location_code: locationCode.value,
      lines: [{ sku: sku.value, counted_qty: countedQty.value }],
    });
    await refreshPositions();
    message.value = "Count adjustment posted.";
    ui.success("Posted", "Count adjustment posted and positions refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Count posting failed.");
  }
}

async function refreshPositions() {
  positions.value = await listPositions();
}

onMounted(async () => {
  try {
    await refreshPositions();
  } catch {
    // Best-effort initial fetch.
  }
});
</script>
