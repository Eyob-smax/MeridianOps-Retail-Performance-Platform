<template>
  <section>
    <h1>Analytics Builder</h1>
    <p>Create reusable dashboard layouts with widget metadata and store/date filters.</p>

    <section class="panel">
      <h2>Create Dashboard</h2>
      <div class="form-grid">
        <input v-model="name" placeholder="Dashboard name" />
        <input v-model="description" placeholder="Description" />
        <input v-model="storeIds" placeholder="Store IDs (comma separated)" />
      </div>
      <button class="btn" @click="onCreate">Create Dashboard</button>
      <p v-if="createdId">Created dashboard ID: {{ createdId }}</p>
    </section>

    <section class="panel">
      <h2>Recent Dashboards</h2>
      <button class="btn" @click="refreshDashboards">Refresh</button>
      <table class="data-table" v-if="dashboards.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Widgets</th>
            <th>Stores</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in dashboards" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.widget_count }}</td>
            <td>{{ row.allowed_store_ids.join(", ") }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";

import {
  createDashboard,
  listDashboards,
  type DashboardSummary,
  type DashboardWidget,
} from "@/services/analytics";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const name = ref("Regional Builder Dashboard");
const description = ref("Store and date linked KPI board");
const storeIds = ref("101,102,103");
const createdId = ref<number | null>(null);
const errorMessage = ref("");
const dashboards = ref<DashboardSummary[]>([]);

const defaultWidgets: DashboardWidget[] = [
  {
    id: "kpi-revenue",
    kind: "kpi",
    title: "Revenue",
    metric: "revenue",
    dimension: null,
    x: 0,
    y: 0,
    w: 4,
    h: 2,
  },
  {
    id: "trend-orders",
    kind: "trend",
    title: "Orders Trend",
    metric: "orders",
    dimension: "date",
    x: 4,
    y: 0,
    w: 8,
    h: 3,
  },
];

async function onCreate() {
  try {
    errorMessage.value = "";
    const allowedStoreIds = storeIds.value
      .split(",")
      .map((v) => Number(v.trim()))
      .filter((v) => Number.isFinite(v) && v > 0);

    const dashboard = await createDashboard({
      name: name.value,
      description: description.value,
      widgets: defaultWidgets,
      allowed_store_ids: allowedStoreIds,
    });
    createdId.value = dashboard.id;
    await refreshDashboards();
    ui.success("Created", `Dashboard ${dashboard.id} created and list refreshed.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Dashboard creation failed.");
  }
}

async function refreshDashboards() {
  dashboards.value = await listDashboards();
}

refreshDashboards().catch(() => {
  // Best-effort initial load.
});
</script>
