<template>
  <section>
    <h1>System Health</h1>
    <div class="health-grid">
      <FeatureCard title="API" :description="apiMessage" />
      <FeatureCard title="Database" :description="dbMessage" />
    </div>
    <button type="button" class="btn" @click="refresh">Refresh</button>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import FeatureCard from "@/components/common/FeatureCard.vue";
import { apiClient } from "@/services/api";

interface HealthPayload {
  api_status: { status: string; detail: string };
  database_status?: { status: string; detail: string } | null;
}

const loading = ref(false);
const errorMessage = ref("");
const payload = ref<HealthPayload | null>(null);

const apiMessage = computed(() => {
  if (!payload.value) return "No data";
  return `${payload.value.api_status.status}: ${payload.value.api_status.detail}`;
});

const dbMessage = computed(() => {
  if (!payload.value?.database_status) return "No data";
  return `${payload.value.database_status.status}: ${payload.value.database_status.detail}`;
});

async function refresh() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const { data } = await apiClient.get<HealthPayload>("/health/database");
    payload.value = data;
  } catch (error) {
    errorMessage.value = "Unable to load health data from backend.";
    console.error(error);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await refresh();
});
</script>
