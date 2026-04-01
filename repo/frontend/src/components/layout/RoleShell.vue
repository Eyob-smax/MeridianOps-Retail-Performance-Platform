<template>
  <div class="layout">
    <TopNav />
    <div class="content-wrap">
      <SideNav />
      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import SideNav from "@/components/navigation/SideNav.vue";
import TopNav from "@/components/navigation/TopNav.vue";
</script>
