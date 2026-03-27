<template>
  <section>
    <h1>Attendance Make-up Requests</h1>
    <p>Submit requests, approve with notes, and export payroll reconciliation CSV.</p>

    <section class="panel">
      <h2>New Request</h2>
      <div class="form-grid">
        <input v-model="businessDate" type="date" />
        <input v-model="reason" placeholder="Reason" />
      </div>
      <button class="btn" @click="onCreateRequest">Submit Request</button>
    </section>

    <section class="panel">
      <h2>Requests</h2>
      <button class="btn" @click="refreshRequests">Refresh</button>
      <table class="data-table" v-if="requests.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>User</th>
            <th>Date</th>
            <th>Status</th>
            <th>Reason</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in requests" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.user_id }}</td>
            <td>{{ row.business_date }}</td>
            <td>{{ row.status }}</td>
            <td>{{ row.reason }}</td>
            <td>
              <button
                class="btn btn-small"
                :disabled="row.status !== 'pending'"
                @click="onApprove(row.id)"
              >
                Approve
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Payroll Export</h2>
      <div class="form-grid">
        <input v-model="exportStart" type="date" />
        <input v-model="exportEnd" type="date" />
      </div>
      <button class="btn" @click="onExport">Generate CSV Preview</button>
      <pre v-if="csvPreview" class="csv-preview">{{ csvPreview }}</pre>
    </section>

    <p v-if="message">{{ message }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  approveMakeupRequest,
  createMakeupRequest,
  exportPayrollCsv,
  listMakeupRequests,
  type AttendanceMakeupRow,
} from "@/services/attendance";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const nowDate = new Date().toISOString().slice(0, 10);

const businessDate = ref(nowDate);
const reason = ref("Missed check-in due to inventory emergency.");
const requests = ref<AttendanceMakeupRow[]>([]);

const exportStart = ref(nowDate);
const exportEnd = ref(nowDate);
const csvPreview = ref("");

const message = ref("");
const errorMessage = ref("");

async function refreshRequests() {
  requests.value = await listMakeupRequests();
}

async function onCreateRequest() {
  try {
    errorMessage.value = "";
    message.value = "";
    await createMakeupRequest({ business_date: businessDate.value, reason: reason.value });
    await refreshRequests();
    message.value = "Request submitted.";
    ui.success("Created", "Make-up request submitted and request list refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to submit make-up request.");
  }
}

async function onApprove(requestId: number) {
  try {
    errorMessage.value = "";
    message.value = "";
    await approveMakeupRequest(requestId, "Approved after manager review.");
    await refreshRequests();
    message.value = `Request ${requestId} approved.`;
    ui.success("Updated", `Request ${requestId} approved and list refreshed.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to approve make-up request.");
  }
}

async function onExport() {
  try {
    errorMessage.value = "";
    csvPreview.value = await exportPayrollCsv(exportStart.value, exportEnd.value);
    ui.success("Posted", "Payroll CSV preview generated.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Payroll export failed.");
  }
}

onMounted(async () => {
  try {
    await refreshRequests();
  } catch {
    // Best-effort initial load.
  }
});
</script>
