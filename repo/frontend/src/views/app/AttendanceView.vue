<template>
  <section>
    <h1>Attendance Check In/Out</h1>
    <p>Uses rotating QR tokens and device binding with configurable attendance rules.</p>

    <section class="panel">
      <h2>Rules</h2>
      <p v-if="rules">
        Tolerance: {{ rules.tolerance_minutes }} min | Auto-break after
        {{ rules.auto_break_after_hours }}h ({{ rules.auto_break_minutes }} min) | Cross-day cutoff
        {{ rules.cross_day_shift_cutoff_hour }}:00 | Penalty {{ rules.late_early_penalty_hours }}h
      </p>
      <button class="btn" @click="refreshRules">Refresh Rules</button>
      <button class="btn" @click="onRotateQr">Rotate QR Token</button>
      <button class="btn" @click="toggleAutoRotation">
        {{ autoRotationActive ? "Stop Auto-Rotation" : "Start Auto-Rotation (30s)" }}
      </button>
      <p v-if="currentQrToken">
        Current QR token: {{ currentQrToken }}
        <span v-if="qrSecondsRemaining > 0"> (expires in {{ qrSecondsRemaining }}s)</span>
        <span v-else-if="currentQrToken && qrSecondsRemaining <= 0" class="error"> (expired)</span>
      </p>
      <p v-if="autoRotationActive">Auto-rotation active — token refreshes every 30 seconds</p>
    </section>

    <section class="panel">
      <h2>Check In</h2>
      <div class="form-grid">
        <input v-model="deviceId" placeholder="Device ID" />
        <input v-model="qrToken" placeholder="QR Token" />
        <input v-model="checkInNfcTag" placeholder="NFC Tag (optional)" />
        <input v-model="checkInLatitude" placeholder="Latitude (optional)" />
        <input v-model="checkInLongitude" placeholder="Longitude (optional)" />
      </div>
      <button class="btn" @click="onCheckIn">Check In</button>
    </section>

    <section class="panel">
      <h2>Check Out</h2>
      <div class="form-grid">
        <input v-model="checkoutQrToken" placeholder="QR Token" />
        <input v-model="checkOutNfcTag" placeholder="NFC Tag (optional)" />
        <input v-model="checkOutLatitude" placeholder="Latitude (optional)" />
        <input v-model="checkOutLongitude" placeholder="Longitude (optional)" />
      </div>
      <button class="btn" @click="onCheckOut">Check Out</button>
      <p v-if="checkoutSummary">
        Business date {{ checkoutSummary.daily_result.business_date }} | Worked
        {{ checkoutSummary.daily_result.worked_hours }}h, Break
        {{ checkoutSummary.daily_result.auto_break_minutes }}m, Penalty
        {{ checkoutSummary.daily_result.penalty_hours }}h
      </p>
    </section>

    <section class="panel">
      <h2>Recent Shifts</h2>
      <button class="btn" @click="refreshShifts">Refresh</button>
      <table class="data-table" v-if="shifts.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Check In</th>
            <th>Check Out</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in shifts" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.check_in_at }}</td>
            <td>{{ row.check_out_at ?? "-" }}</td>
            <td>{{ row.status }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="message">{{ message }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";

import {
  attendanceCheckIn,
  attendanceCheckOut,
  getAttendanceRules,
  listMyShifts,
  rotateAttendanceQr,
  type AttendanceRule,
  type AttendanceShiftRow,
} from "@/services/attendance";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const rules = ref<AttendanceRule | null>(null);
const shifts = ref<AttendanceShiftRow[]>([]);
const deviceId = ref("DEVICE-EMP-1");
const qrToken = ref("");
const checkoutQrToken = ref("");
const checkInNfcTag = ref("");
const checkInLatitude = ref("");
const checkInLongitude = ref("");
const checkOutNfcTag = ref("");
const checkOutLatitude = ref("");
const checkOutLongitude = ref("");
const currentQrToken = ref("");
const checkoutSummary = ref<{
  shift: AttendanceShiftRow;
  daily_result: {
      business_date: string;
      worked_hours: string;
      auto_break_minutes: number;
      penalty_hours: string;
  };
} | null>(null);

const autoRotationActive = ref(false);
const qrSecondsRemaining = ref(0);
let autoRotationInterval: ReturnType<typeof setInterval> | null = null;
let countdownInterval: ReturnType<typeof setInterval> | null = null;

const message = ref("");
const errorMessage = ref("");

async function refreshRules() {
  rules.value = await getAttendanceRules();
}

async function refreshShifts() {
  shifts.value = await listMyShifts(30);
}

async function onRotateQr() {
  try {
    errorMessage.value = "";
    const row = await rotateAttendanceQr();
    currentQrToken.value = row.token;
    qrToken.value = row.token;
    checkoutQrToken.value = row.token;
    qrSecondsRemaining.value = 30;
    ui.success("Posted", "New attendance QR token generated.");
  } catch (error) {
    errorMessage.value = notifyError(error, "QR token rotation failed.");
  }
}

function startCountdown() {
  if (countdownInterval) clearInterval(countdownInterval);
  countdownInterval = setInterval(() => {
    if (qrSecondsRemaining.value > 0) {
      qrSecondsRemaining.value--;
    }
  }, 1000);
}

function stopCountdown() {
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
}

async function toggleAutoRotation() {
  if (autoRotationActive.value) {
    autoRotationActive.value = false;
    if (autoRotationInterval) {
      clearInterval(autoRotationInterval);
      autoRotationInterval = null;
    }
    stopCountdown();
    return;
  }

  autoRotationActive.value = true;
  await onRotateQr();
  startCountdown();
  autoRotationInterval = setInterval(async () => {
    await onRotateQr();
  }, 30000);
}

async function onCheckIn() {
  try {
    errorMessage.value = "";
    message.value = "";
    await attendanceCheckIn({
      device_id: deviceId.value,
      qr_token: qrToken.value,
      nfc_tag: checkInNfcTag.value || undefined,
      check_in_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
      scheduled_start_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
      scheduled_end_at: new Date().toISOString(),
      latitude: checkInLatitude.value || undefined,
      longitude: checkInLongitude.value || undefined,
    });
    await refreshShifts();
    message.value = "Checked in.";
    ui.success("Posted", "Check-in posted and shifts list refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Check-in failed.");
  }
}

async function onCheckOut() {
  try {
    errorMessage.value = "";
    message.value = "";
    checkoutSummary.value = await attendanceCheckOut({
      device_id: deviceId.value,
      qr_token: checkoutQrToken.value,
      nfc_tag: checkOutNfcTag.value || undefined,
      check_out_at: new Date().toISOString(),
      latitude: checkOutLatitude.value || undefined,
      longitude: checkOutLongitude.value || undefined,
    });
    await refreshShifts();
    message.value = "Checked out.";
    ui.success("Posted", "Check-out posted and shifts list refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Check-out failed.");
  }
}

onMounted(async () => {
  try {
    await refreshRules();
    await refreshShifts();
  } catch {
    // Best-effort initial load.
  }
});

onUnmounted(() => {
  if (autoRotationInterval) clearInterval(autoRotationInterval);
  stopCountdown();
});
</script>
