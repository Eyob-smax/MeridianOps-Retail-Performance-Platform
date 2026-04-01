<template>
  <transition name="fade">
    <div v-if="ui.isLoading" class="global-loading">
      <div class="global-loading__bar" />
      <div class="global-loading__text">Processing request...</div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
</script>
