from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_roles
from app.core.errors import bad_request
from app.db.session import get_db
from app.schemas.auth import AuthUser
from app.schemas.orders import (
    OrderCreateRequest,
    OrderResponse,
    OrderTransitionRequest,
)
from app.services.order_service import (
    OrderError,
    cancel_order,
    complete_order,
    create_order,
    get_order,
    list_orders,
    reserve_order,
)

router = APIRouter(prefix="/orders", tags=["orders"])

_ORDER_ROLES = {"administrator", "store_manager", "cashier"}


@router.post("", response_model=OrderResponse)
def order_create(
    payload: OrderCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ORDER_ROLES)),
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        result = create_order(db, payload, current_user)
        db.commit()
        return result
    except OrderError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/reserve", response_model=OrderResponse)
def order_reserve(
    payload: OrderTransitionRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ORDER_ROLES)),
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        result = reserve_order(db, payload.order_reference, current_user)
        db.commit()
        return result
    except OrderError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/complete", response_model=OrderResponse)
def order_complete(
    payload: OrderTransitionRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ORDER_ROLES)),
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        result = complete_order(db, payload.order_reference, current_user)
        db.commit()
        return result
    except OrderError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/cancel", response_model=OrderResponse)
def order_cancel(
    payload: OrderTransitionRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_ORDER_ROLES)),
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        result = cancel_order(db, payload.order_reference, current_user)
        db.commit()
        return result
    except OrderError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("", response_model=list[OrderResponse])
def order_list(
    limit: int = Query(default=50, ge=1, le=500),
    current_user: AuthUser = Depends(require_roles(_ORDER_ROLES | {"inventory_clerk"})),
    db: Session = Depends(get_db),
) -> list[OrderResponse]:
    return list_orders(db, store_id=current_user.store_id, limit=limit)


@router.get("/{order_reference}", response_model=OrderResponse)
def order_detail(
    order_reference: str,
    current_user: AuthUser = Depends(require_roles(_ORDER_ROLES | {"inventory_clerk"})),
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        return get_order(db, order_reference, store_id=current_user.store_id)
    except OrderError as exc:
        raise bad_request(str(exc))
