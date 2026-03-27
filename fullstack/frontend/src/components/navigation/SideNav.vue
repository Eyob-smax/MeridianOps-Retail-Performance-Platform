<template>
  <aside class="side-nav">
    <RouterLink
      v-for="item in visibleItems"
      :key="item.path"
      :to="item.path"
      class="nav-link"
      active-class="nav-link-active"
    >
      {{ item.name }}
    </RouterLink>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { navigationItems } from "@/app/navigation";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();

const visibleItems = computed(() => {
  if (!auth.role) return [];
  return navigationItems.filter((item) => item.roles.includes(auth.role!));
});
</script>
