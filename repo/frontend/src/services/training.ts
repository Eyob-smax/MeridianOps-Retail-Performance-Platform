import { apiClient } from "@/services/api";

export interface TopicRow {
  id: number;
  code: string;
  name: string;
  difficulty: "easy" | "medium" | "hard";
}

export interface ReviewQueueEntry {
  topic_code: string;
  topic_name: string;
  due_date: string;
  recommendation_reason: string;
}

export interface TrainingStat {
  topic_code: string;
  attempts: number;
  correct: number;
  hit_rate: number;
}

export interface TrainingTrendPoint {
  date: string;
  attempts: number;
  hit_rate: number;
}

export async function listTrainingTopics() {
  const { data } = await apiClient.get<TopicRow[]>("/training/topics");
  return data;
}

export async function createTrainingTopic(payload: {
  code: string;
  name: string;
  difficulty: "easy" | "medium" | "hard";
}) {
  const { data } = await apiClient.post<TopicRow>("/training/topics", payload);
  return data;
}

export async function createTrainingQuestion(payload: {
  topic_code: string;
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_answer: string;
}) {
  const { data } = await apiClient.post<{ question_id: number }>("/training/questions", payload);
  return data;
}

export async function assignTrainingTopic(payload: {
  employee_username: string;
  topic_code: string;
}) {
  const { data } = await apiClient.post<{ status: string }>("/training/assignments", payload);
  return data;
}

export async function listReviewQueue() {
  const { data } = await apiClient.get<ReviewQueueEntry[]>("/training/review-queue");
  return data;
}

export async function submitTrainingAttempt(payload: {
  topic_code: string;
  question_id: number;
  selected_answer: string;
}) {
  const { data } = await apiClient.post<{
    correct: boolean;
    recommendation_reason: string;
    next_review_date: string;
  }>("/training/attempts", payload);
  return data;
}

export async function listTrainingStats() {
  const { data } = await apiClient.get<TrainingStat[]>("/training/stats");
  return data;
}

export async function listTrainingTrends(days = 14) {
  const { data } = await apiClient.get<TrainingTrendPoint[]>("/training/trends", {
    params: { days },
  });
  return data;
}
