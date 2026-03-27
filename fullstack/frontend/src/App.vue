<template>
  <GlobalLoading />
  <ToastStack />
  <RouterView />
</template>

<script setup lang="ts">
import GlobalLoading from "@/components/common/GlobalLoading.vue";
import ToastStack from "@/components/common/ToastStack.vue";
</script>
