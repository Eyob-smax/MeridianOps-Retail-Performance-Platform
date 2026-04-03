import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    InventoryItem,
    InventoryLocation,
    InventoryReservation,
    Order,
    OrderLine,
)
from app.schemas.auth import AuthUser
from app.schemas.inventory import ReservationCreateRequest, ReservationReleaseRequest
from app.schemas.orders import (
    OrderCreateRequest,
    OrderLineResponse,
    OrderResponse,
)
from app.services.audit_service import audit_event
from app.services.inventory_service import (
    InventoryError,
    create_reservation,
    release_reservation,
)

logger = logging.getLogger("meridianops.orders")

VALID_TRANSITIONS = {
    "created": {"reserved", "cancelled"},
    "reserved": {"completed", "cancelled"},
}


class OrderError(ValueError):
    pass


def _get_order_by_reference(db: Session, order_reference: str, store_id: int | None = None) -> Order:
    stmt = select(Order).where(Order.order_reference == order_reference.strip())
    if store_id is not None:
        stmt = stmt.where(Order.store_id == store_id)
    order = db.execute(stmt).scalar_one_or_none()
    if not order:
        raise OrderError("Order not found")
    return order


def _build_order_response(db: Session, order: Order) -> OrderResponse:
    lines = db.execute(select(OrderLine).where(OrderLine.order_id == order.id)).scalars().all()
    line_responses = []
    for line in lines:
        item = db.execute(select(InventoryItem).where(InventoryItem.id == line.item_id)).scalar_one()
        location = db.execute(select(InventoryLocation).where(InventoryLocation.id == line.location_id)).scalar_one()
        line_responses.append(
            OrderLineResponse(
                id=line.id,
                sku=item.sku,
                location_code=location.code,
                quantity=line.quantity,
                unit_price=line.unit_price,
                reservation_id=line.reservation_id,
            )
        )
    return OrderResponse(
        id=order.id,
        order_reference=order.order_reference,
        status=order.status,
        total_amount=order.total_amount,
        store_id=order.store_id,
        lines=line_responses,
        created_at=order.created_at,
    )


def create_order(db: Session, payload: OrderCreateRequest, current_user: AuthUser) -> OrderResponse:
    existing = db.execute(
        select(Order.id).where(Order.order_reference == payload.order_reference.strip())
    ).scalar_one_or_none()
    if existing:
        raise OrderError("Order reference already exists")

    total = Decimal("0.00")
    for line in payload.lines:
        total += (line.quantity * line.unit_price).quantize(Decimal("0.01"))

    order = Order(
        store_id=current_user.store_id,
        order_reference=payload.order_reference.strip(),
        status="created",
        total_amount=total,
        created_by_user_id=current_user.id,
    )
    db.add(order)
    db.flush()

    for line_input in payload.lines:
        item = db.execute(
            select(InventoryItem).where(InventoryItem.sku == line_input.sku.strip().upper())
        ).scalar_one_or_none()
        if not item:
            raise OrderError(f"Item not found for SKU {line_input.sku}")
        location = db.execute(
            select(InventoryLocation).where(InventoryLocation.code == line_input.location_code.strip().upper())
        ).scalar_one_or_none()
        if not location:
            raise OrderError(f"Location not found for code {line_input.location_code}")

        order_line = OrderLine(
            order_id=order.id,
            item_id=item.id,
            location_id=location.id,
            quantity=line_input.quantity,
            unit_price=line_input.unit_price,
        )
        db.add(order_line)
        db.flush()

    audit_event(
        db,
        action="order.created",
        resource_type="order",
        resource_id=str(order.id),
        actor_user_id=current_user.id,
        detail={"order_reference": order.order_reference, "total_amount": str(total), "line_count": len(payload.lines)},
    )

    return _build_order_response(db, order)


def reserve_order(db: Session, order_reference: str, current_user: AuthUser) -> OrderResponse:
    order = _get_order_by_reference(db, order_reference, store_id=current_user.store_id)

    if order.status not in VALID_TRANSITIONS or "reserved" not in VALID_TRANSITIONS.get(order.status, set()):
        raise OrderError(f"Cannot reserve order in status '{order.status}'")

    lines = db.execute(select(OrderLine).where(OrderLine.order_id == order.id)).scalars().all()
    if not lines:
        raise OrderError("Order has no lines to reserve")

    for line in lines:
        item = db.execute(select(InventoryItem).where(InventoryItem.id == line.item_id)).scalar_one()
        location = db.execute(select(InventoryLocation).where(InventoryLocation.id == line.location_id)).scalar_one()

        reservation_request = ReservationCreateRequest(
            order_reference=order.order_reference,
            sku=item.sku,
            location_code=location.code,
            quantity=line.quantity,
        )
        try:
            reservation_response = create_reservation(db, reservation_request, current_user)
            line.reservation_id = reservation_response.id
        except InventoryError as exc:
            raise OrderError(f"Reservation failed for SKU {item.sku}: {exc}")

    order.status = "reserved"

    audit_event(
        db,
        action="order.reserved",
        resource_type="order",
        resource_id=str(order.id),
        actor_user_id=current_user.id,
        detail={"order_reference": order.order_reference, "line_count": len(lines)},
    )

    return _build_order_response(db, order)


def complete_order(db: Session, order_reference: str, current_user: AuthUser) -> OrderResponse:
    order = _get_order_by_reference(db, order_reference, store_id=current_user.store_id)

    if order.status not in VALID_TRANSITIONS or "completed" not in VALID_TRANSITIONS.get(order.status, set()):
        raise OrderError(f"Cannot complete order in status '{order.status}'")

    # Release reservations (stock leaves reserved pool — fulfilled)
    lines = db.execute(select(OrderLine).where(OrderLine.order_id == order.id)).scalars().all()
    for line in lines:
        if line.reservation_id:
            release_request = ReservationReleaseRequest(reservation_id=line.reservation_id)
            release_reservation(db, release_request, current_user)

    order.status = "completed"

    audit_event(
        db,
        action="order.completed",
        resource_type="order",
        resource_id=str(order.id),
        actor_user_id=current_user.id,
        detail={"order_reference": order.order_reference},
    )

    return _build_order_response(db, order)


def cancel_order(db: Session, order_reference: str, current_user: AuthUser) -> OrderResponse:
    order = _get_order_by_reference(db, order_reference, store_id=current_user.store_id)

    if order.status not in VALID_TRANSITIONS or "cancelled" not in VALID_TRANSITIONS.get(order.status, set()):
        raise OrderError(f"Cannot cancel order in status '{order.status}'")

    # Release reservations back to available stock
    lines = db.execute(select(OrderLine).where(OrderLine.order_id == order.id)).scalars().all()
    for line in lines:
        if line.reservation_id:
            release_request = ReservationReleaseRequest(reservation_id=line.reservation_id)
            release_reservation(db, release_request, current_user)

    order.status = "cancelled"

    audit_event(
        db,
        action="order.cancelled",
        resource_type="order",
        resource_id=str(order.id),
        actor_user_id=current_user.id,
        detail={"order_reference": order.order_reference},
    )

    return _build_order_response(db, order)


def get_order(db: Session, order_reference: str, store_id: int | None = None) -> OrderResponse:
    order = _get_order_by_reference(db, order_reference, store_id=store_id)
    return _build_order_response(db, order)


def list_orders(db: Session, store_id: int | None = None, limit: int = 50) -> list[OrderResponse]:
    stmt = select(Order).order_by(Order.id.desc()).limit(limit)
    if store_id is not None:
        stmt = stmt.where(Order.store_id == store_id)
    orders = db.execute(stmt).scalars().all()
    return [_build_order_response(db, order) for order in orders]
