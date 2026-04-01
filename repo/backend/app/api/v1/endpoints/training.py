from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_roles
from app.core.errors import bad_request
from app.db.session import get_db
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
from app.services.training_service import (
    TrainingError,
    assign_topic,
    create_question,
    create_topic,
    get_review_queue,
    list_topics,
    submit_attempt,
    topic_stats,
    trend_points,
)

router = APIRouter(prefix="/training", tags=["training"])

_SUPERVISOR_ROLES = {"administrator", "store_manager"}


@router.get("/topics", response_model=list[TopicResponse])
def training_topics(
    current_user: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES | {"employee"})),
    db: Session = Depends(get_db),
) -> list[TopicResponse]:
    return list_topics(db, store_id=current_user.store_id)


@router.post("/topics", response_model=TopicResponse)
def training_create_topic(
    payload: TopicCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES)),
    db: Session = Depends(get_db),
) -> TopicResponse:
    try:
        response = create_topic(db, payload, current_user)
        db.commit()
        return response
    except TrainingError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/questions")
def training_create_question(
    payload: QuestionCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    try:
        question_id = create_question(db, payload, current_user)
        db.commit()
        return {"question_id": question_id}
    except TrainingError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/assignments")
def training_assign_topic(
    payload: AssignmentRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        assign_topic(db, payload, current_user)
        db.commit()
        return {"status": "assigned"}
    except TrainingError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("/review-queue", response_model=list[ReviewQueueEntry])
def training_review_queue(
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES | {"employee"})),
    db: Session = Depends(get_db),
) -> list[ReviewQueueEntry]:
    return get_review_queue(db, current_user)


@router.post("/attempts", response_model=AttemptSubmitResponse)
def training_submit_attempt(
    payload: AttemptSubmitRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES | {"employee"})),
    db: Session = Depends(get_db),
) -> AttemptSubmitResponse:
    try:
        response = submit_attempt(db, payload, current_user)
        db.commit()
        return response
    except TrainingError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("/stats", response_model=list[TopicStatsResponse])
def training_stats(
    current_user: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES)),
    db: Session = Depends(get_db),
) -> list[TopicStatsResponse]:
    return topic_stats(db, store_id=current_user.store_id)


@router.get("/trends", response_model=list[TrainingTrendPoint])
def training_trends(
    days: int = Query(default=14, ge=1, le=90),
    current_user: AuthUser = Depends(require_roles(_SUPERVISOR_ROLES)),
    db: Session = Depends(get_db),
) -> list[TrainingTrendPoint]:
    return trend_points(db, days=days, store_id=current_user.store_id)
