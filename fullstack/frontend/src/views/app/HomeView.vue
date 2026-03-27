<template>
  <section>
    <h1>Operations Home</h1>
    <p class="hint">Live command center for daily retail operations.</p>

    <div class="home-grid">
      <article class="card metric-card">
        <h2>Session</h2>
        <p><strong>User:</strong> {{ auth.displayName || auth.username || "Unknown" }}</p>
        <p><strong>Role:</strong> {{ primaryRoleLabel }}</p>
        <p><strong>Updated:</strong> {{ updatedAt }}</p>
      </article>

      <article class="card metric-card">
        <h2>Platform Health</h2>
        <p>
          <strong>API:</strong>
          <span :class="apiHealth.ok ? 'ok' : 'error'">{{ apiHealth.label }}</span>
        </p>
        <p>
          <strong>Database:</strong>
          <span :class="dbHealth.ok ? 'ok' : 'error'">{{ dbHealth.label }}</span>
        </p>
      </article>

      <article class="card metric-card">
        <h2>Operational Snapshot</h2>
        <p><strong>Campaigns:</strong> {{ snapshot.campaigns }}</p>
        <p><strong>Members:</strong> {{ snapshot.members }}</p>
        <p><strong>Inventory Positions:</strong> {{ snapshot.positions }}</p>
      </article>

      <article class="card metric-card">
        <h2>Scheduler</h2>
        <p><strong>Status:</strong> {{ schedulerStatus }}</p>
        <p><strong>Next Run:</strong> {{ schedulerNextRun }}</p>
      </article>
    </div>

    <section class="panel">
      <h2>Priority Actions</h2>
      <div class="quick-links">
        <router-link
          v-for="item in quickActions"
          :key="item.path"
          class="quick-link"
          :to="item.path"
        >
          {{ item.name }}
        </router-link>
      </div>
    </section>

    <section class="panel">
      <h2>Shift Checklist</h2>
      <ul class="checklist">
        <li>Validate health checks before opening operations.</li>
        <li>Review today campaign limits and active windows.</li>
        <li>Confirm reserved stock against outbound orders.</li>
        <li>Run attendance queue review for active staff.</li>
      </ul>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref } from "vue";

import { navigationItems } from "@/app/navigation";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

type HealthState = { ok: boolean; label: string };

const auth = useAuthStore();

const apiHealth = ref<HealthState>({ ok: false, label: "Checking..." });
const dbHealth = ref<HealthState>({ ok: false, label: "Checking..." });
const snapshot = ref({ campaigns: "-", members: "-", positions: "-" });
const schedulerStatus = ref("Not available");
const schedulerNextRun = ref("-");
const updatedAt = ref("-");
const errorMessage = ref("");

const roleLabels: Record<string, string> = {
  administrator: "Administrator",
  store_manager: "Store Manager",
  inventory_clerk: "Inventory Clerk",
  cashier: "Cashier",
  employee: "Employee",
};

const primaryRole = computed(() => auth.roles[0] ?? "employee");
const primaryRoleLabel = computed(() => roleLabels[primaryRole.value] ?? "Employee");

const quickActions = computed(() => {
  return navigationItems
    .filter((item) => item.path !== "/app/home")
    .filter((item) => item.roles.some((role) => auth.roles.includes(role)))
    .slice(0, 8);
});

function formatNow(): string {
  return new Date().toLocaleString();
}

function safeError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? "Request failed");
  }
  return "Request failed";
}

async function loadHealth() {
  try {
    await apiClient.get("/health");
    apiHealth.value = { ok: true, label: "Online" };
  } catch {
    apiHealth.value = { ok: false, label: "Unavailable" };
  }

  try {
    await apiClient.get("/health/database");
    dbHealth.value = { ok: true, label: "Connected" };
  } catch {
    dbHealth.value = { ok: false, label: "Degraded" };
  }
}

async function loadRoleAwareSnapshot() {
  const canViewCampaigns = auth.roles.some((role) =>
    ["administrator", "store_manager"].includes(role),
  );
  const canViewMembers = auth.roles.some((role) =>
    ["administrator", "store_manager", "cashier"].includes(role),
  );
  const canViewInventory = auth.roles.some((role) =>
    ["administrator", "store_manager", "inventory_clerk", "cashier"].includes(role),
  );
  const canViewScheduler = auth.roles.some((role) =>
    ["administrator", "store_manager"].includes(role),
  );

  if (canViewCampaigns) {
    try {
      const { data } = await apiClient.get<Array<unknown>>("/campaigns");
      snapshot.value.campaigns = String(data.length);
    } catch {
      snapshot.value.campaigns = "N/A";
    }
  } else {
    snapshot.value.campaigns = "Restricted";
  }

  if (canViewMembers) {
    try {
      const { data } = await apiClient.get<Array<unknown>>("/members");
      snapshot.value.members = String(data.length);
    } catch {
      snapshot.value.members = "N/A";
    }
  } else {
    snapshot.value.members = "Restricted";
  }

  if (canViewInventory) {
    try {
      const { data } = await apiClient.get<Array<unknown>>("/inventory/positions");
      snapshot.value.positions = String(data.length);
    } catch {
      snapshot.value.positions = "N/A";
    }
  } else {
    snapshot.value.positions = "Restricted";
  }

  if (canViewScheduler) {
    try {
      const { data } = await apiClient.get<{ enabled: boolean; next_run_at: string | null }>(
        "/ops/scheduler/status",
      );
      schedulerStatus.value = data.enabled ? "Enabled" : "Disabled";
      schedulerNextRun.value = data.next_run_at
        ? new Date(data.next_run_at).toLocaleString()
        : "Not scheduled";
    } catch {
      schedulerStatus.value = "Unavailable";
      schedulerNextRun.value = "-";
    }
  } else {
    schedulerStatus.value = "Restricted";
    schedulerNextRun.value = "Restricted";
  }
}

onMounted(async () => {
  try {
    errorMessage.value = "";
    await loadHealth();
    await loadRoleAwareSnapshot();
    updatedAt.value = formatNow();
  } catch (error) {
    errorMessage.value = safeError(error);
  }
});
</script>
