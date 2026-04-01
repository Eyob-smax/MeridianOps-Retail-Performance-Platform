<template>
  <section>
    <h1>Training Review Queue</h1>
    <p>
      Employees can review due topics and submit quiz attempts with explainable next-review reasons.
    </p>

    <section class="panel">
      <h2>Queue</h2>
      <button class="btn" @click="refreshQueue">Refresh</button>
      <table class="data-table" v-if="queue.length > 0">
        <thead>
          <tr>
            <th>Topic</th>
            <th>Due Date</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in queue" :key="`${row.topic_code}-${row.due_date}`">
            <td>{{ row.topic_code }} - {{ row.topic_name }}</td>
            <td>{{ row.due_date }}</td>
            <td>{{ row.recommendation_reason }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Submit Attempt</h2>
      <div class="form-grid">
        <input v-model="topicCode" placeholder="Topic code" />
        <input v-model.number="questionId" type="number" placeholder="Question ID" />
        <input v-model="selectedAnswer" placeholder="Selected answer" />
      </div>
      <button class="btn" @click="onSubmitAttempt">Submit Attempt</button>
      <p v-if="attemptResult">
        {{ attemptResult.correct ? "Correct" : "Incorrect" }}
        | {{ attemptResult.recommendation_reason }} | next {{ attemptResult.next_review_date }}
      </p>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listReviewQueue, submitTrainingAttempt, type ReviewQueueEntry } from "@/services/training";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const queue = ref<ReviewQueueEntry[]>([]);
const topicCode = ref("CASH-POLICY");
const questionId = ref(1);
const selectedAnswer = ref("Store manager");
const attemptResult = ref<{
  correct: boolean;
  recommendation_reason: string;
  next_review_date: string;
} | null>(null);
const errorMessage = ref("");

async function refreshQueue() {
  queue.value = await listReviewQueue();
}

async function onSubmitAttempt() {
  try {
    errorMessage.value = "";
    attemptResult.value = await submitTrainingAttempt({
      topic_code: topicCode.value,
      question_id: Number(questionId.value),
      selected_answer: selectedAnswer.value,
    });
    await refreshQueue();
    ui.success("Posted", "Training attempt submitted and review queue updated.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Training attempt submission failed.");
  }
}

onMounted(async () => {
  try {
    await refreshQueue();
  } catch {
    // Best-effort initial load.
  }
});
</script>
