<template>
  <div class="toast-stack">
    <div v-for="toast in ui.toasts" :key="toast.id" class="toast" :class="`toast-${toast.type}`">
      <div class="toast__header">
        <strong>{{ toast.title }}</strong>
        <button class="toast__close" @click="ui.removeToast(toast.id)">x</button>
      </div>
      <p>{{ toast.message }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
</script>
