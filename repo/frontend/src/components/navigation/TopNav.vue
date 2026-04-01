<template>
  <header class="top-nav">
    <div>
      <p class="brand">{{ appName }}</p>
      <p v-if="auth.isAuthenticated" class="sub">{{ auth.displayName }} ({{ roleLabel }})</p>
      <p v-else class="sub">Signed out</p>
    </div>
    <div class="role-picker" v-if="auth.isAuthenticated">
      <button type="button" class="btn" @click="onLogout">Logout</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const appName = import.meta.env.VITE_APP_NAME ?? "MeridianOps Retail Performance";

const roleLabel = computed(() => (auth.role ? auth.role.replace("_", " ") : "no role"));

async function onLogout() {
  await auth.signOut();
  await router.push("/login");
}
</script>
