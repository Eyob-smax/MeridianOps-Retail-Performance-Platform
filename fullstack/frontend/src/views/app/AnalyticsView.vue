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
        <button class="btn btn-small" @click="onExportFile('csv')">Export CSV</button>
        <button class="btn btn-small" @click="onExportFile('png')">Export PNG</button>
        <button class="btn btn-small" @click="onExportFile('pdf')">Export PDF</button>
        <button class="btn btn-small" @click="onCreateShare">Create Share Link</button>
      </div>
      <div class="form-grid" style="margin-top: 12px">
        <select v-model.number="selectedStoreIdForDrill">
          <option :value="0">Select store for drilldown</option>
          <option v-for="row in selectedDashboard.data.by_store ?? []" :key="`drill-store-${row.store_id}`" :value="row.store_id">
            {{ row.store_name }} ({{ row.store_id }})
          </option>
        </select>
        <input v-model="selectedDateForDrill" type="date" />
        <button class="btn btn-small" @click="onStoreDrilldown">Drill by Store</button>
        <button class="btn btn-small" @click="onDateDrilldown">Drill by Date</button>
      </div>
      <p v-if="exportMeta">
        Export: {{ exportMeta.filename }} ({{ exportMeta.content_type }},
        {{ exportMeta.size_bytes }} bytes)
      </p>
      <p v-if="lastDownloadedFileName">Downloaded: {{ lastDownloadedFileName }}</p>
      <p v-if="shareLink">Share URL: {{ shareLink }}</p>

      <section class="panel" v-if="storeDrilldown">
        <h3>Store Drilldown</h3>
        <p>
          {{ storeDrilldown.store_name }} ({{ storeDrilldown.store_id }}) | Orders: {{ storeDrilldown.orders }} | Revenue:
          {{ storeDrilldown.revenue }} | Margin: {{ storeDrilldown.gross_margin }}
        </p>
      </section>

      <section class="panel" v-if="dateDrilldown">
        <h3>Date Drilldown</h3>
        <p>
          {{ dateDrilldown.business_date }} | Orders: {{ dateDrilldown.orders }} | Revenue: {{ dateDrilldown.revenue }} |
          Margin: {{ dateDrilldown.gross_margin }}
        </p>
      </section>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  createDashboardShareLink,
  exportDashboardFile,
  exportDashboardMetadata,
  getDashboardDateDrilldown,
  getDashboard,
  getDashboardStoreDrilldown,
  listDashboards,
  type DateDrillDown,
  type DashboardDetail,
  type DashboardSummary,
  type StoreDrillDown,
} from "@/services/analytics";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const dashboards = ref<DashboardSummary[]>([]);
const selectedDashboard = ref<DashboardDetail | null>(null);
const exportMeta = ref<{ filename: string; content_type: string; size_bytes: number } | null>(null);
const shareLink = ref("");
const lastDownloadedFileName = ref("");
const selectedStoreIdForDrill = ref(0);
const selectedDateForDrill = ref("");
const storeDrilldown = ref<StoreDrillDown | null>(null);
const dateDrilldown = ref<DateDrillDown | null>(null);
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
    lastDownloadedFileName.value = "";
    selectedStoreIdForDrill.value = 0;
    selectedDateForDrill.value = selectedDashboard.value.data.filters.start_date;
    storeDrilldown.value = null;
    dateDrilldown.value = null;
    ui.info("Loaded", `Dashboard ${dashboardId} loaded.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to load dashboard details.");
  }
}

function _downloadBlob(blob: Blob, filename: string) {
  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(blobUrl);
}

async function onExportFile(format: "csv" | "png" | "pdf") {
  if (!selectedDashboard.value) return;
  try {
    errorMessage.value = "";
    const payload = await exportDashboardFile(selectedDashboard.value.id, format);
    _downloadBlob(payload.blob, payload.filename);
    lastDownloadedFileName.value = payload.filename;
    ui.success("Downloaded", `${format.toUpperCase()} export downloaded.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to export dashboard file.");
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

async function onStoreDrilldown() {
  if (!selectedDashboard.value || !selectedStoreIdForDrill.value) return;
  try {
    errorMessage.value = "";
    storeDrilldown.value = await getDashboardStoreDrilldown(selectedDashboard.value.id, selectedStoreIdForDrill.value);
    ui.info("Loaded", `Store drilldown ready for ${storeDrilldown.value.store_name}.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to load store drilldown.");
  }
}

async function onDateDrilldown() {
  if (!selectedDashboard.value || !selectedDateForDrill.value) return;
  try {
    errorMessage.value = "";
    dateDrilldown.value = await getDashboardDateDrilldown(selectedDashboard.value.id, selectedDateForDrill.value);
    ui.info("Loaded", `Date drilldown ready for ${dateDrilldown.value.business_date}.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to load date drilldown.");
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
