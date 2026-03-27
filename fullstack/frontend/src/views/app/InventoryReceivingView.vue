<template>
  <section>
    <h1>Inventory Receiving</h1>
    <p>Create items and locations, receive inbound stock, and track reserved quantities.</p>

    <section class="panel">
      <h2>Setup</h2>
      <div class="form-grid">
        <input v-model="newSku" placeholder="SKU (e.g. SKU-100)" />
        <input v-model="newItemName" placeholder="Item name" />
        <button class="btn" @click="onCreateItem">Create Item</button>

        <input v-model="newLocationCode" placeholder="Location code (e.g. MAIN)" />
        <input v-model="newLocationName" placeholder="Location name" />
        <button class="btn" @click="onCreateLocation">Create Location</button>
      </div>
    </section>

    <section class="panel">
      <h2>Post Receiving</h2>
      <div class="form-grid">
        <input v-model="locationCode" placeholder="Location code" />
        <input v-model="receiveSku" placeholder="SKU" />
        <input v-model="receiveQty" placeholder="Quantity" />
        <input v-model="receiveBatch" placeholder="Batch no (optional)" />
      </div>
      <button class="btn" @click="onReceive">Post Receiving</button>
    </section>

    <section class="panel">
      <h2>Reserve Stock</h2>
      <div class="form-grid">
        <input v-model="orderReference" placeholder="Order reference" />
        <input v-model="reservationSku" placeholder="SKU" />
        <input v-model="reservationLocation" placeholder="Location code" />
        <input v-model="reservationQty" placeholder="Quantity" />
      </div>
      <button class="btn" @click="onReserve">Create Reservation</button>
      <div class="inline-actions" v-if="lastReservationId">
        <span>Reservation {{ lastReservationId }}</span>
        <button class="btn btn-small" @click="onReleaseReservation">Release</button>
      </div>
    </section>

    <section class="panel">
      <h2>Positions</h2>
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

import {
  createInventoryItem,
  createInventoryLocation,
  createReservation,
  listPositions,
  postReceiving,
  releaseReservation,
  type InventoryPosition,
} from "@/services/inventory";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const newSku = ref("SKU-100");
const newItemName = ref("Sparkling Water 500ml");
const newLocationCode = ref("MAIN");
const newLocationName = ref("Main Floor");

const locationCode = ref("MAIN");
const receiveSku = ref("SKU-100");
const receiveQty = ref("20.000");
const receiveBatch = ref("");

const orderReference = ref("ORDER-INV-1");
const reservationSku = ref("SKU-100");
const reservationLocation = ref("MAIN");
const reservationQty = ref("5.000");
const lastReservationId = ref<number | null>(null);

const positions = ref<InventoryPosition[]>([]);
const errorMessage = ref("");
const message = ref("");

async function onCreateItem() {
  try {
    errorMessage.value = "";
    message.value = "";
    await createInventoryItem({ sku: newSku.value, name: newItemName.value, unit: "ea" });
    await refreshPositions();
    message.value = `Created item ${newSku.value}`;
    ui.success("Created", `Item ${newSku.value} created successfully.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Item creation failed.");
  }
}

async function onCreateLocation() {
  try {
    errorMessage.value = "";
    message.value = "";
    await createInventoryLocation({ code: newLocationCode.value, name: newLocationName.value });
    await refreshPositions();
    message.value = `Created location ${newLocationCode.value}`;
    ui.success("Created", `Location ${newLocationCode.value} created successfully.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Location creation failed.");
  }
}

async function onReceive() {
  try {
    errorMessage.value = "";
    message.value = "";
    await postReceiving({
      location_code: locationCode.value,
      lines: [
        {
          sku: receiveSku.value,
          quantity: receiveQty.value,
          batch_no: receiveBatch.value || undefined,
        },
      ],
    });
    await refreshPositions();
    message.value = "Receiving document posted.";
    ui.success("Posted", "Receiving document posted and positions refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Receiving post failed.");
  }
}

async function onReserve() {
  try {
    errorMessage.value = "";
    message.value = "";
    const row = await createReservation({
      order_reference: orderReference.value,
      sku: reservationSku.value,
      location_code: reservationLocation.value,
      quantity: reservationQty.value,
    });
    lastReservationId.value = row.id;
    await refreshPositions();
    message.value = `Reservation ${row.id} created.`;
    ui.success("Created", `Reservation ${row.id} created and positions refreshed.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Reservation creation failed.");
  }
}

async function onReleaseReservation() {
  if (!lastReservationId.value) return;
  try {
    errorMessage.value = "";
    message.value = "";
    await releaseReservation(lastReservationId.value);
    await refreshPositions();
    message.value = `Reservation ${lastReservationId.value} released.`;
    ui.success("Posted", `Reservation ${lastReservationId.value} released successfully.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Reservation release failed.");
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
