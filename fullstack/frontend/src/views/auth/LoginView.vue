<template>
  <section class="login-card">
    <h1>Login</h1>
    <p>
      Use one of the local bootstrap users (for example: `admin`, `manager`, `clerk`, `cashier`,
      `employee`).
    </p>
    <form @submit.prevent="onSubmit">
      <label for="username">Username</label>
      <input id="username" v-model.trim="username" required maxlength="64" />

      <label for="password">Password</label>
      <input
        id="password"
        v-model="password"
        required
        type="password"
        minlength="12"
        maxlength="256"
      />

      <button class="btn" type="submit" :disabled="auth.loading">Sign In</button>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p class="hint">Default password for seed users: `ChangeMeNow123`.</p>
    </form>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { getErrorMessage } from "@/utils/feedback";

const auth = useAuthStore();
const router = useRouter();

const username = ref("admin");
const password = ref("ChangeMeNow123");
const errorMessage = ref("");

async function onSubmit() {
  errorMessage.value = "";
  try {
    await auth.signIn(username.value, password.value);
    await router.push("/app/home");
  } catch (error) {
    errorMessage.value = getErrorMessage(error, "Unable to sign in.");
  }
}
</script>
