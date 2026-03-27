<template>
  <section>
    <h1>Analytics Dashboards</h1>
    <p>
      View dashboard summaries, drill into details, verify exports, and generate read-only links.
    </p>

    <section class="panel">
      <h2>Dashboards</h2>
      <button class="btn" @click="refreshDashboards">Refresh</button>
      <table class="data-table" v-if="dashboards.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Widgets</th>
            <th>Stores</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in dashboards" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.widget_count }}</td>
            <td>{{ row.allowed_store_ids.join(", ") }}</td>
            <td><button class="btn btn-small" @click="onSelectDashboard(row.id)">Open</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel" v-if="selectedDashboard">
      <h2>Dashboard Detail: {{ selectedDashboard.name }}</h2>
      <p>
        Orders: {{ selectedDashboard.data.totals.orders }} | Revenue:
        {{ selectedDashboard.data.totals.revenue }} | Gross Margin:
        {{ selectedDashboard.data.totals.gross_margin }}
      </p>
      <div class="inline-actions">
        <button class="btn btn-small" @click="onExportMeta('csv')">CSV Meta</button>
        <button class="btn btn-small" @click="onExportMeta('png')">PNG Meta</button>
        <button class="btn btn-small" @click="onExportMeta('pdf')">PDF Meta</button>
        <button class="btn btn-small" @click="onCreateShare">Create Share Link</button>
      </div>
      <p v-if="exportMeta">
        Export: {{ exportMeta.filename }} ({{ exportMeta.content_type }},
        {{ exportMeta.size_bytes }} bytes)
      </p>
      <p v-if="shareLink">Share URL: {{ shareLink }}</p>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  createDashboardShareLink,
  exportDashboardMetadata,
  getDashboard,
  listDashboards,
  type DashboardDetail,
  type DashboardSummary,
} from "@/services/analytics";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const dashboards = ref<DashboardSummary[]>([]);
const selectedDashboard = ref<DashboardDetail | null>(null);
const exportMeta = ref<{ filename: string; content_type: string; size_bytes: number } | null>(null);
const shareLink = ref("");
const errorMessage = ref("");

async function refreshDashboards() {
  dashboards.value = await listDashboards();
}

async function onSelectDashboard(dashboardId: number) {
  try {
    errorMessage.value = "";
    selectedDashboard.value = await getDashboard(dashboardId);
    exportMeta.value = null;
    shareLink.value = "";
    ui.info("Loaded", `Dashboard ${dashboardId} loaded.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to load dashboard details.");
  }
}

async function onExportMeta(format: "csv" | "png" | "pdf") {
  if (!selectedDashboard.value) return;
  try {
    errorMessage.value = "";
    exportMeta.value = await exportDashboardMetadata(selectedDashboard.value.id, format);
    ui.success("Posted", `${format.toUpperCase()} export metadata generated.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to load export metadata.");
  }
}

async function onCreateShare() {
  if (!selectedDashboard.value) return;
  try {
    errorMessage.value = "";
    const row = await createDashboardShareLink(selectedDashboard.value.id);
    shareLink.value = row.share_url;
    ui.success("Created", "Read-only share link created.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to create share link.");
  }
}

onMounted(async () => {
  try {
    await refreshDashboards();
  } catch {
    // Best-effort initial load.
  }
});
</script>
