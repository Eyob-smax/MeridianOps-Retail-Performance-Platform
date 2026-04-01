import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from "@/services/api";
import { createTrainingTopic, listReviewQueue, submitTrainingAttempt } from "@/services/training";

describe("training service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates topic with expected payload", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { id: 1, code: "CASH", name: "Cash", difficulty: "easy" },
    });

    const row = await createTrainingTopic({ code: "CASH", name: "Cash", difficulty: "easy" });

    expect(apiClient.post).toHaveBeenCalledWith("/training/topics", {
      code: "CASH",
      name: "Cash",
      difficulty: "easy",
    });
    expect(row.code).toBe("CASH");
  });

  it("loads review queue", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: [
        {
          topic_code: "SAFE-CASH",
          topic_name: "Safe Cash",
          due_date: "2026-03-27",
          recommendation_reason: "review in 3 days",
        },
      ],
    });

    const queue = await listReviewQueue();

    expect(apiClient.get).toHaveBeenCalledWith("/training/review-queue");
    expect(queue[0].topic_code).toBe("SAFE-CASH");
  });

  it("submits attempt and returns recommendation", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        correct: false,
        recommendation_reason: "review in 1 days due to two recent misses",
        next_review_date: "2026-03-28",
      },
    });

    const response = await submitTrainingAttempt({
      topic_code: "SAFE-CASH",
      question_id: 9,
      selected_answer: "Wrong",
    });

    expect(apiClient.post).toHaveBeenCalledWith("/training/attempts", {
      topic_code: "SAFE-CASH",
      question_id: 9,
      selected_answer: "Wrong",
    });
    expect(response.correct).toBe(false);
  });
});
