from datetime import date, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core.security import ROLE_EMPLOYEE
from app.db.models import QuizAssignment, QuizAttempt, QuizQuestion, QuizTopic, ReviewQueueSnapshot, SpacedRepetitionState, User
from app.db.models import UserRole
from app.schemas.auth import AuthUser
from app.schemas.training import (
    AssignmentRequest,
    AttemptSubmitRequest,
    AttemptSubmitResponse,
    QuestionCreateRequest,
    ReviewQueueEntry,
    TopicCreateRequest,
    TopicResponse,
    TopicStatsResponse,
    TrainingTrendPoint,
)
from app.services.audit_service import audit_event


class TrainingError(ValueError):
    pass


_DIFFICULTY_DAY_WEIGHT = {
    "easy": 1,
    "medium": 0,
    "hard": -1,
}


def _normalize_topic_code(code: str) -> str:
    return code.strip().upper()


def _get_topic(db: Session, topic_code: str, store_id: int | None = None) -> QuizTopic:
    stmt = select(QuizTopic).where(QuizTopic.code == _normalize_topic_code(topic_code))
    if store_id is not None:
        stmt = stmt.where(QuizTopic.store_id == store_id)
    topic = db.execute(stmt).scalar_one_or_none()
    if not topic:
        raise TrainingError("Topic not found")
    return topic


def list_topics(db: Session, store_id: int | None = None) -> list[TopicResponse]:
    stmt = select(QuizTopic).order_by(QuizTopic.code.asc())
    if store_id is not None:
        stmt = stmt.where(QuizTopic.store_id == store_id)
    topics = db.execute(stmt).scalars().all()
    return [TopicResponse(id=row.id, code=row.code, name=row.name, difficulty=row.difficulty) for row in topics]


def create_topic(db: Session, payload: TopicCreateRequest, current_user: AuthUser) -> TopicResponse:
    code = _normalize_topic_code(payload.code)
    exists_stmt = select(QuizTopic.id).where(QuizTopic.code == code)
    if current_user.store_id is not None:
        exists_stmt = exists_stmt.where(QuizTopic.store_id == current_user.store_id)
    exists = db.execute(exists_stmt).scalar_one_or_none()
    if exists:
        raise TrainingError("Topic code already exists")

    topic = QuizTopic(
        store_id=current_user.store_id,
        code=code,
        name=payload.name.strip(),
        difficulty=payload.difficulty.value,
        created_by_user_id=current_user.id,
    )
    db.add(topic)
    db.flush()

    audit_event(
        db,
        action="training.topic.created",
        resource_type="quiz_topic",
        resource_id=str(topic.id),
        actor_user_id=current_user.id,
        detail={"code": topic.code, "name": topic.name, "difficulty": topic.difficulty},
    )

    return TopicResponse(id=topic.id, code=topic.code, name=topic.name, difficulty=payload.difficulty)


def create_question(db: Session, payload: QuestionCreateRequest, current_user: AuthUser) -> int:
    topic = _get_topic(db, payload.topic_code, store_id=current_user.store_id)
    question = QuizQuestion(
        store_id=topic.store_id,
        topic_id=topic.id,
        question_text=payload.question_text.strip(),
        option_a=payload.option_a,
        option_b=payload.option_b,
        option_c=payload.option_c,
        option_d=payload.option_d,
        correct_answer=payload.correct_answer,
    )
    db.add(question)
    db.flush()

    audit_event(
        db,
        action="training.question.created",
        resource_type="quiz_question",
        resource_id=str(question.id),
        actor_user_id=current_user.id,
        detail={"topic_code": topic.code},
    )

    return question.id


def assign_topic(db: Session, payload: AssignmentRequest, current_user: AuthUser) -> None:
    topic = _get_topic(db, payload.topic_code, store_id=current_user.store_id)
    employee = db.execute(select(User).where(User.username == payload.employee_username.lower())).scalar_one_or_none()
    if not employee:
        raise TrainingError("Employee not found")
    if current_user.store_id is not None and employee.store_id != current_user.store_id:
        raise TrainingError("Employee not found")

    has_employee_role = db.execute(
        select(UserRole.id)
        .where(
            UserRole.user_id == employee.id,
            UserRole.role_name == ROLE_EMPLOYEE,
        )
        .limit(1)
    ).scalar_one_or_none()
    if not has_employee_role:
        raise TrainingError("Assignee must have employee role")

    existing = db.execute(
        select(QuizAssignment)
        .where(
            QuizAssignment.employee_user_id == employee.id,
            QuizAssignment.topic_id == topic.id,
        )
        .limit(1)
    ).scalar_one_or_none()

    if not existing:
        db.add(
            QuizAssignment(
                store_id=topic.store_id,
                employee_user_id=employee.id,
                topic_id=topic.id,
                assigned_by_user_id=current_user.id,
                active=True,
            )
        )

    state = db.execute(
        select(SpacedRepetitionState)
        .where(
            SpacedRepetitionState.employee_user_id == employee.id,
            SpacedRepetitionState.topic_id == topic.id,
        )
        .limit(1)
    ).scalar_one_or_none()

    if not state:
        db.add(
            SpacedRepetitionState(
                store_id=topic.store_id,
                employee_user_id=employee.id,
                topic_id=topic.id,
                next_review_date=date.today(),
                interval_days=1,
                consecutive_correct=0,
                recent_misses=0,
                ease_factor=2.5,
                recommendation_reason="Initial review",
            )
        )

    audit_event(
        db,
        action="training.assignment.created",
        resource_type="quiz_assignment",
        resource_id=f"{employee.id}:{topic.id}",
        actor_user_id=current_user.id,
        detail={"employee_username": employee.username, "topic_code": topic.code},
    )


def get_review_queue(db: Session, current_user: AuthUser) -> list[ReviewQueueEntry]:
    rows = db.execute(
        select(SpacedRepetitionState, QuizTopic)
        .join(QuizTopic, QuizTopic.id == SpacedRepetitionState.topic_id)
        .where(SpacedRepetitionState.employee_user_id == current_user.id)
        .where(
            SpacedRepetitionState.store_id == current_user.store_id
            if current_user.store_id is not None
            else True
        )
        .order_by(SpacedRepetitionState.next_review_date.asc(), QuizTopic.code.asc())
    ).all()

    queue: list[ReviewQueueEntry] = []
    for state, topic in rows:
        queue.append(
            ReviewQueueEntry(
                topic_code=topic.code,
                topic_name=topic.name,
                due_date=state.next_review_date,
                recommendation_reason=state.recommendation_reason,
            )
        )
    return queue


def _next_interval_days(difficulty: str, interval_days: int, consecutive_correct: int, recent_misses: int, correct: bool) -> int:
    base = max(1, interval_days)
    if correct:
        return max(1, base + 1 + _DIFFICULTY_DAY_WEIGHT.get(difficulty, 0) + min(consecutive_correct, 2))
    return max(1, base - 1 + _DIFFICULTY_DAY_WEIGHT.get(difficulty, 0) - min(recent_misses, 1))


def submit_attempt(db: Session, payload: AttemptSubmitRequest, current_user: AuthUser) -> AttemptSubmitResponse:
    topic = _get_topic(db, payload.topic_code, store_id=current_user.store_id)
    assignment = db.execute(
        select(QuizAssignment)
        .where(
            QuizAssignment.employee_user_id == current_user.id,
            QuizAssignment.topic_id == topic.id,
            QuizAssignment.active.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()
    if not assignment:
        raise TrainingError("No active assignment for this topic")

    question = db.execute(
        select(QuizQuestion).where(QuizQuestion.id == payload.question_id, QuizQuestion.topic_id == topic.id)
    ).scalar_one_or_none()
    if not question:
        raise TrainingError("Question not found")

    correct = payload.selected_answer.strip() == question.correct_answer

    db.add(
        QuizAttempt(
            store_id=topic.store_id,
            employee_user_id=current_user.id,
            topic_id=topic.id,
            question_id=question.id,
            selected_answer=payload.selected_answer,
            is_correct=correct,
        )
    )

    state = db.execute(
        select(SpacedRepetitionState)
        .where(
            SpacedRepetitionState.employee_user_id == current_user.id,
            SpacedRepetitionState.topic_id == topic.id,
        )
        .limit(1)
    ).scalar_one_or_none()

    if not state:
        state = SpacedRepetitionState(
            store_id=topic.store_id,
            employee_user_id=current_user.id,
            topic_id=topic.id,
            next_review_date=date.today(),
            interval_days=1,
            consecutive_correct=0,
            recent_misses=0,
            ease_factor=2.5,
            recommendation_reason="Initial review",
        )
        db.add(state)
        db.flush()

    if correct:
        state.consecutive_correct += 1
        state.recent_misses = max(0, state.recent_misses - 1)
    else:
        state.consecutive_correct = 0
        state.recent_misses += 1

    interval_days = _next_interval_days(
        topic.difficulty,
        state.interval_days,
        state.consecutive_correct,
        state.recent_misses,
        correct,
    )
    state.interval_days = interval_days
    state.next_review_date = date.today() + timedelta(days=interval_days)

    if not correct and state.recent_misses >= 2:
        reason = f"review in {interval_days} days due to two recent misses"
    elif correct and state.consecutive_correct >= 2:
        reason = f"review in {interval_days} days due to recent mastery"
    else:
        reason = f"review in {interval_days} days based on {topic.difficulty} difficulty"

    state.recommendation_reason = reason

    db.add(
        ReviewQueueSnapshot(
            store_id=topic.store_id,
            employee_user_id=current_user.id,
            topic_id=topic.id,
            due_date=state.next_review_date,
            recommendation_reason=reason,
        )
    )

    return AttemptSubmitResponse(correct=correct, recommendation_reason=reason, next_review_date=state.next_review_date)


def topic_stats(db: Session, store_id: int | None = None) -> list[TopicStatsResponse]:
    rows = db.execute(
        select(
            QuizTopic.code,
            func.count(QuizAttempt.id),
            func.coalesce(func.sum(case((QuizAttempt.is_correct.is_(True), 1), else_=0)), 0),
        )
        .select_from(QuizTopic)
        .outerjoin(QuizAttempt, QuizAttempt.topic_id == QuizTopic.id)
        .where(QuizTopic.store_id == store_id if store_id is not None else True)
        .group_by(QuizTopic.code)
        .order_by(QuizTopic.code.asc())
    ).all()

    output: list[TopicStatsResponse] = []
    for topic_code, attempts, correct in rows:
        attempts_i = int(attempts or 0)
        correct_i = int(correct or 0)
        hit_rate = (correct_i / attempts_i) if attempts_i else 0.0
        output.append(
            TopicStatsResponse(topic_code=topic_code, attempts=attempts_i, correct=correct_i, hit_rate=round(hit_rate, 4))
        )
    return output


def trend_points(db: Session, days: int = 14, store_id: int | None = None) -> list[TrainingTrendPoint]:
    start = date.today() - timedelta(days=max(1, days - 1))
    rows = db.execute(
        select(
            func.date(QuizAttempt.attempted_at),
            func.count(QuizAttempt.id),
            func.coalesce(func.sum(case((QuizAttempt.is_correct.is_(True), 1), else_=0)), 0),
        )
        .where(and_(func.date(QuizAttempt.attempted_at) >= start, func.date(QuizAttempt.attempted_at) <= date.today()))
        .where(QuizAttempt.store_id == store_id if store_id is not None else True)
        .group_by(func.date(QuizAttempt.attempted_at))
        .order_by(func.date(QuizAttempt.attempted_at).asc())
    ).all()

    output: list[TrainingTrendPoint] = []
    for row_date, attempts, correct in rows:
        attempts_i = int(attempts or 0)
        correct_i = int(correct or 0)
        hit_rate = (correct_i / attempts_i) if attempts_i else 0.0
        output.append(TrainingTrendPoint(date=row_date, attempts=attempts_i, hit_rate=round(hit_rate, 4)))
    return output
