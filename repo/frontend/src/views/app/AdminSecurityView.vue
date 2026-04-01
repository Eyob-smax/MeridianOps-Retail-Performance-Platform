<template>
  <section>
    <h1>Admin Security</h1>
    <p>
      Review authentication policy and attendance penalty controls for local security governance.
    </p>

    <section class="panel" v-if="policy">
      <h2>Authentication Policy</h2>
      <ul>
        <li>Minimum password length: {{ policy.min_password_length }}</li>
        <li>Lockout attempts: {{ policy.max_failed_attempts }}</li>
        <li>Lockout window: {{ policy.lockout_minutes }} minutes</li>
        <li>Session duration: {{ policy.session_minutes }} minutes</li>
        <li>Masking default: {{ policy.masking_enabled_default ? "enabled" : "disabled" }}</li>
        <li>Field encryption key configured: {{ policy.encryption_enabled ? "yes" : "no" }}</li>
      </ul>
    </section>

    <section class="panel" v-if="rules">
      <h2>Attendance Rule Controls</h2>
      <div class="form-grid">
        <input v-model.number="rules.tolerance_minutes" type="number" min="0" max="120" />
        <input v-model.number="rules.auto_break_after_hours" type="number" min="1" max="24" />
        <input v-model.number="rules.auto_break_minutes" type="number" min="0" max="180" />
        <input v-model.number="rules.cross_day_shift_cutoff_hour" type="number" min="0" max="23" />
        <input v-model="rules.late_early_penalty_hours" />
      </div>
      <button class="btn" @click="onSaveRules">Save Rule Config</button>
    </section>

    <p v-if="message">{{ message }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  getAttendanceRules,
  updateAttendanceRules,
  type AttendanceRule,
} from "@/services/attendance";
import { fetchSecurityPolicy, type SecurityPolicy } from "@/services/auth";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const policy = ref<SecurityPolicy | null>(null);
const rules = ref<AttendanceRule | null>(null);
const message = ref("");
const errorMessage = ref("");

async function refreshData() {
  policy.value = await fetchSecurityPolicy();
  rules.value = await getAttendanceRules();
}

async function onSaveRules() {
  if (!rules.value) return;
  try {
    errorMessage.value = "";
    message.value = "";
    rules.value = await updateAttendanceRules(rules.value);
    message.value = "Rule configuration updated.";
    ui.success("Updated", "Attendance rule configuration updated successfully.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to update attendance rules.");
  }
}

onMounted(async () => {
  try {
    await refreshData();
  } catch {
    // Best-effort initial load.
  }
});
</script>
