from datetime import date

from pydantic import BaseModel, Field

from app.types.business import QuizDifficulty


class TopicCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=120)
    difficulty: QuizDifficulty = QuizDifficulty.MEDIUM


class TopicResponse(BaseModel):
    id: int
    code: str
    name: str
    difficulty: QuizDifficulty


class QuestionCreateRequest(BaseModel):
    topic_code: str
    question_text: str = Field(min_length=5)
    option_a: str = Field(min_length=1, max_length=255)
    option_b: str = Field(min_length=1, max_length=255)
    option_c: str = Field(min_length=1, max_length=255)
    option_d: str = Field(min_length=1, max_length=255)
    correct_answer: str = Field(min_length=1, max_length=255)


class AssignmentRequest(BaseModel):
    employee_username: str
    topic_code: str


class ReviewQueueEntry(BaseModel):
    topic_code: str
    topic_name: str
    due_date: date
    recommendation_reason: str


class AttemptSubmitRequest(BaseModel):
    topic_code: str
    question_id: int
    selected_answer: str


class AttemptSubmitResponse(BaseModel):
    correct: bool
    recommendation_reason: str
    next_review_date: date


class TopicStatsResponse(BaseModel):
    topic_code: str
    attempts: int
    correct: int
    hit_rate: float


class TrainingTrendPoint(BaseModel):
    date: date
    attempts: int
    hit_rate: float
