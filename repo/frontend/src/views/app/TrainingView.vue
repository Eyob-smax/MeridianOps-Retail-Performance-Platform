<template>
  <section>
    <h1>Training Management</h1>
    <p>Create topics, add quiz questions, assign employees, and monitor hit-rate trends.</p>

    <section class="panel">
      <h2>Create Topic</h2>
      <div class="form-grid">
        <input v-model="topicCode" placeholder="Topic code" />
        <input v-model="topicName" placeholder="Topic name" />
        <select v-model="topicDifficulty">
          <option value="easy">easy</option>
          <option value="medium">medium</option>
          <option value="hard">hard</option>
        </select>
      </div>
      <button class="btn" @click="onCreateTopic">Create Topic</button>
    </section>

    <section class="panel">
      <h2>Add Question</h2>
      <div class="form-grid">
        <input v-model="questionTopicCode" placeholder="Topic code" />
        <input v-model="questionText" placeholder="Question" />
        <input v-model="optionA" placeholder="Option A" />
        <input v-model="optionB" placeholder="Option B" />
        <input v-model="optionC" placeholder="Option C" />
        <input v-model="optionD" placeholder="Option D" />
        <input v-model="correctAnswer" placeholder="Correct answer" />
      </div>
      <button class="btn" @click="onCreateQuestion">Add Question</button>
    </section>

    <section class="panel">
      <h2>Assign Topic</h2>
      <div class="form-grid">
        <input v-model="assignmentEmployee" placeholder="Employee username" />
        <input v-model="assignmentTopicCode" placeholder="Topic code" />
      </div>
      <button class="btn" @click="onAssignTopic">Assign</button>
    </section>

    <section class="panel">
      <h2>Topic Stats</h2>
      <button class="btn" @click="refreshData">Refresh</button>
      <table class="data-table" v-if="stats.length > 0">
        <thead>
          <tr>
            <th>Topic</th>
            <th>Attempts</th>
            <th>Correct</th>
            <th>Hit Rate</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in stats" :key="row.topic_code">
            <td>{{ row.topic_code }}</td>
            <td>{{ row.attempts }}</td>
            <td>{{ row.correct }}</td>
            <td>{{ (row.hit_rate * 100).toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
      <table class="data-table" v-if="trends.length > 0">
        <thead>
          <tr>
            <th>Date</th>
            <th>Attempts</th>
            <th>Hit Rate</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in trends" :key="row.date">
            <td>{{ row.date }}</td>
            <td>{{ row.attempts }}</td>
            <td>{{ (row.hit_rate * 100).toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="message">{{ message }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  assignTrainingTopic,
  createTrainingQuestion,
  createTrainingTopic,
  listTrainingStats,
  listTrainingTrends,
  type TrainingStat,
  type TrainingTrendPoint,
} from "@/services/training";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const topicCode = ref("CASH-POLICY");
const topicName = ref("Cash Handling Policy");
const topicDifficulty = ref<"easy" | "medium" | "hard">("medium");

const questionTopicCode = ref("CASH-POLICY");
const questionText = ref("Who can approve a manual refund?");
const optionA = ref("Any cashier");
const optionB = ref("Store manager");
const optionC = ref("Customer service only");
const optionD = ref("No one");
const correctAnswer = ref("Store manager");

const assignmentEmployee = ref("employee");
const assignmentTopicCode = ref("CASH-POLICY");

const stats = ref<TrainingStat[]>([]);
const trends = ref<TrainingTrendPoint[]>([]);
const message = ref("");
const errorMessage = ref("");

async function refreshData() {
  stats.value = await listTrainingStats();
  trends.value = await listTrainingTrends(14);
}

async function onCreateTopic() {
  try {
    message.value = "";
    errorMessage.value = "";
    await createTrainingTopic({
      code: topicCode.value,
      name: topicName.value,
      difficulty: topicDifficulty.value,
    });
    message.value = `Topic ${topicCode.value} created.`;
    await refreshData();
    ui.success("Created", `Topic ${topicCode.value} created and stats refreshed.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Topic creation failed.");
  }
}

async function onCreateQuestion() {
  try {
    message.value = "";
    errorMessage.value = "";
    await createTrainingQuestion({
      topic_code: questionTopicCode.value,
      question_text: questionText.value,
      option_a: optionA.value,
      option_b: optionB.value,
      option_c: optionC.value,
      option_d: optionD.value,
      correct_answer: correctAnswer.value,
    });
    await refreshData();
    message.value = "Question created.";
    ui.success("Created", "Training question created and stats refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Question creation failed.");
  }
}

async function onAssignTopic() {
  try {
    message.value = "";
    errorMessage.value = "";
    await assignTrainingTopic({
      employee_username: assignmentEmployee.value,
      topic_code: assignmentTopicCode.value,
    });
    await refreshData();
    message.value = `Assigned ${assignmentTopicCode.value} to ${assignmentEmployee.value}.`;
    ui.success("Posted", "Training assignment posted and metrics refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Topic assignment failed.");
  }
}

onMounted(async () => {
  try {
    await refreshData();
  } catch {
    // Best-effort initial load.
  }
});
</script>
