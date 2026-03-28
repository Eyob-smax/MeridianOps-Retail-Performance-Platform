<template>
  <section>
    <h1>Shared Dashboard</h1>
    <p v-if="dashboard">
      {{ dashboard.name }} | Read-only access for stores {{ dashboard.allowed_store_ids.join(", ") }}
    </p>

    <section v-if="dashboard" class="panel">
      <h2>{{ dashboard.name }}</h2>
      <p v-if="dashboard.description">{{ dashboard.description }}</p>
      <p>
        Orders: {{ dashboard.data.totals.orders }} | Revenue: {{ dashboard.data.totals.revenue }} | Margin:
        {{ dashboard.data.totals.gross_margin }}
      </p>
      <p>
        Window: {{ dashboard.data.filters.start_date }} to {{ dashboard.data.filters.end_date }}
      </p>
    </section>

    <section v-if="dashboard?.data.by_store?.length" class="panel">
      <h2>Store Breakdown</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Store</th>
            <th>Orders</th>
            <th>Revenue</th>
            <th>Margin</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in dashboard.data.by_store" :key="row.store_id">
            <td>{{ row.store_name }}</td>
            <td>{{ row.orders }}</td>
            <td>{{ row.revenue }}</td>
            <td>{{ row.gross_margin }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="dashboard?.data.rows?.length" class="panel">
      <h2>Rows</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Store</th>
            <th>Orders</th>
            <th>Revenue</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in dashboard.data.rows.slice(0, 20)" :key="`${row.store_id}-${row.business_date}-${index}`">
            <td>{{ row.business_date }}</td>
            <td>{{ row.store_name }}</td>
            <td>{{ row.orders }}</td>
            <td>{{ row.revenue }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getSharedDashboard, type SharedDashboardDetail } from "@/services/analytics";
import { notifyError } from "@/utils/feedback";

const route = useRoute();

const dashboard = ref<SharedDashboardDetail | null>(null);
const errorMessage = ref("");

async function loadSharedDashboard() {
  try {
    errorMessage.value = "";
    const token = String(route.params.token ?? "");
    dashboard.value = await getSharedDashboard(token);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to load shared dashboard.");
  }
}

onMounted(async () => {
  await loadSharedDashboard();
});
</script>
