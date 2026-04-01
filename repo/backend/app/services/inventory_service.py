from decimal import Decimal
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    InventoryDocument,
    InventoryDocumentLine,
    InventoryItem,
    InventoryLedger,
    InventoryLocation,
    InventoryReservation,
    User,
)
from app.schemas.auth import AuthUser
from app.schemas.inventory import (
    CountRequest,
    InventoryDocumentResponse,
    InventoryItemCreateRequest,
    InventoryItemResponse,
    InventoryLedgerEntryResponse,
    InventoryLocationCreateRequest,
    InventoryLocationResponse,
    InventoryPositionResponse,
    ReceivingRequest,
    ReservationCreateRequest,
    ReservationReleaseRequest,
    ReservationResponse,
    TransferRequest,
)
from app.core.masking import mask_record
from app.services.audit_service import audit_event
from app.services.inventory_math import quantize_qty


logger = logging.getLogger("meridianops.inventory")
_SENSITIVE_LOG_KEYS = {"order_reference"}


class InventoryError(ValueError):
    pass


def _normalize_sku(value: str) -> str:
    return value.strip().upper()


def _normalize_code(value: str) -> str:
    return value.strip().upper()


def _get_item_by_sku(db: Session, sku: str) -> InventoryItem:
    row = db.execute(select(InventoryItem).where(InventoryItem.sku == _normalize_sku(sku))).scalar_one_or_none()
    if not row:
        raise InventoryError(f"Item not found for SKU {sku}")
    return row


def _get_location_by_code(db: Session, code: str, store_id: int | None = None) -> InventoryLocation:
    stmt = select(InventoryLocation).where(InventoryLocation.code == _normalize_code(code))
    if store_id is not None:
        stmt = stmt.where(InventoryLocation.store_id == store_id)
    row = db.execute(stmt).scalar_one_or_none()
    if not row:
        raise InventoryError(f"Location not found for code {code}")
    return row


def _position_totals(db: Session, item_id: int, location_id: int) -> tuple[Decimal, Decimal, Decimal]:
    qty, reserved = db.execute(
        select(
            func.coalesce(func.sum(InventoryLedger.quantity_delta), Decimal("0")),
            func.coalesce(func.sum(InventoryLedger.reservation_delta), Decimal("0")),
        ).where(InventoryLedger.item_id == item_id, InventoryLedger.location_id == location_id)
    ).one()
    on_hand = quantize_qty(Decimal(qty or 0))
    reserved_qty = quantize_qty(Decimal(reserved or 0))
    available = quantize_qty(on_hand - reserved_qty)
    return on_hand, reserved_qty, available


def _position_response(db: Session, item: InventoryItem, location: InventoryLocation) -> InventoryPositionResponse:
    on_hand, reserved_qty, available = _position_totals(db, item.id, location.id)
    return InventoryPositionResponse(
        sku=item.sku,
        item_name=item.name,
        location_code=location.code,
        on_hand_qty=on_hand,
        reserved_qty=reserved_qty,
        available_qty=available,
    )


def create_item(db: Session, payload: InventoryItemCreateRequest, current_user: AuthUser) -> InventoryItemResponse:
    sku = _normalize_sku(payload.sku)
    exists = db.execute(select(InventoryItem.id).where(InventoryItem.sku == sku)).scalar_one_or_none()
    if exists:
        raise InventoryError("SKU already exists")

    row = InventoryItem(
        sku=sku,
        name=payload.name.strip(),
        unit=payload.unit.strip(),
        batch_tracking_enabled=payload.batch_tracking_enabled,
        expiry_tracking_enabled=payload.expiry_tracking_enabled,
    )
    db.add(row)
    db.flush()

    audit_event(
        db,
        action="inventory.item.created",
        resource_type="inventory_item",
        resource_id=str(row.id),
        actor_user_id=current_user.id,
        detail={"sku": row.sku, "name": row.name},
    )

    return InventoryItemResponse(
        id=row.id,
        sku=row.sku,
        name=row.name,
        unit=row.unit,
        batch_tracking_enabled=row.batch_tracking_enabled,
        expiry_tracking_enabled=row.expiry_tracking_enabled,
    )


def create_location(db: Session, payload: InventoryLocationCreateRequest, current_user: AuthUser) -> InventoryLocationResponse:
    code = _normalize_code(payload.code)
    exists = db.execute(select(InventoryLocation.id).where(InventoryLocation.code == code)).scalar_one_or_none()
    if exists:
        raise InventoryError("Location code already exists")

    row = InventoryLocation(code=code, name=payload.name.strip(), store_id=current_user.store_id)
    db.add(row)
    db.flush()

    audit_event(
        db,
        action="inventory.location.created",
        resource_type="inventory_location",
        resource_id=str(row.id),
        actor_user_id=current_user.id,
        detail={"code": row.code, "name": row.name},
    )

    return InventoryLocationResponse(id=row.id, code=row.code, name=row.name)


def post_receiving(db: Session, payload: ReceivingRequest, current_user: AuthUser) -> InventoryDocumentResponse:
    location = _get_location_by_code(db, payload.location_code, store_id=current_user.store_id)
    if not payload.lines:
        raise InventoryError("At least one line is required")

    document = InventoryDocument(
        doc_type="receiving",
        status="posted",
        target_location_id=location.id,
        store_id=location.store_id,
        note=payload.note,
        operator_user_id=current_user.id,
    )
    db.add(document)
    db.flush()

    for line in payload.lines:
        item = _get_item_by_sku(db, line.sku)
        if line.batch_no and not item.batch_tracking_enabled:
            raise InventoryError(f"Item {item.sku} does not allow batch numbers")
        if line.expiry_date and not item.expiry_tracking_enabled:
            raise InventoryError(f"Item {item.sku} does not allow expiry dates")

        qty = quantize_qty(line.quantity)
        doc_line = InventoryDocumentLine(
            document_id=document.id,
            item_id=item.id,
            quantity=qty,
            batch_no=line.batch_no,
            expiry_date=line.expiry_date,
            note=line.note,
        )
        db.add(doc_line)
        db.flush()

        db.add(
            InventoryLedger(
                item_id=item.id,
                location_id=location.id,
                store_id=location.store_id,
                entry_type="receiving",
                quantity_delta=qty,
                reservation_delta=Decimal("0"),
                document_id=document.id,
                document_line_id=doc_line.id,
                batch_no=line.batch_no,
                expiry_date=line.expiry_date,
            )
        )

    audit_event(
        db,
        action="inventory.receiving.posted",
        resource_type="inventory_document",
        resource_id=str(document.id),
        actor_user_id=current_user.id,
        detail={"location_code": location.code, "line_count": len(payload.lines)},
    )

    return InventoryDocumentResponse(document_id=document.id, doc_type=document.doc_type, status=document.status)


def post_transfer(db: Session, payload: TransferRequest, current_user: AuthUser) -> InventoryDocumentResponse:
    source = _get_location_by_code(db, payload.source_location_code, store_id=current_user.store_id)
    target = _get_location_by_code(db, payload.target_location_code, store_id=current_user.store_id)
    if source.id == target.id:
        raise InventoryError("Source and target locations must be different")
    if not payload.lines:
        raise InventoryError("At least one line is required")

    document = InventoryDocument(
        doc_type="transfer",
        status="posted",
        source_location_id=source.id,
        target_location_id=target.id,
        store_id=source.store_id,
        note=payload.note,
        operator_user_id=current_user.id,
    )
    db.add(document)
    db.flush()

    for line in payload.lines:
        item = _get_item_by_sku(db, line.sku)
        qty = quantize_qty(line.quantity)
        _, _, available = _position_totals(db, item.id, source.id)
        if available < qty:
            raise InventoryError(f"Insufficient available stock for SKU {item.sku}")

        doc_line = InventoryDocumentLine(
            document_id=document.id,
            item_id=item.id,
            quantity=qty,
            batch_no=line.batch_no,
            expiry_date=line.expiry_date,
            note=line.note,
        )
        db.add(doc_line)
        db.flush()

        db.add(
            InventoryLedger(
                item_id=item.id,
                location_id=source.id,
                store_id=source.store_id,
                entry_type="transfer_out",
                quantity_delta=-qty,
                reservation_delta=Decimal("0"),
                document_id=document.id,
                document_line_id=doc_line.id,
                batch_no=line.batch_no,
                expiry_date=line.expiry_date,
            )
        )
        db.add(
            InventoryLedger(
                item_id=item.id,
                location_id=target.id,
                store_id=target.store_id,
                entry_type="transfer_in",
                quantity_delta=qty,
                reservation_delta=Decimal("0"),
                document_id=document.id,
                document_line_id=doc_line.id,
                batch_no=line.batch_no,
                expiry_date=line.expiry_date,
            )
        )

    audit_event(
        db,
        action="inventory.transfer.posted",
        resource_type="inventory_document",
        resource_id=str(document.id),
        actor_user_id=current_user.id,
        detail={"source": source.code, "target": target.code, "line_count": len(payload.lines)},
    )

    return InventoryDocumentResponse(document_id=document.id, doc_type=document.doc_type, status=document.status)


def post_count(db: Session, payload: CountRequest, current_user: AuthUser) -> InventoryDocumentResponse:
    location = _get_location_by_code(db, payload.location_code, store_id=current_user.store_id)
    if not payload.lines:
        raise InventoryError("At least one line is required")

    document = InventoryDocument(
        doc_type="stock_count",
        status="posted",
        target_location_id=location.id,
        store_id=location.store_id,
        note=payload.note,
        operator_user_id=current_user.id,
    )
    db.add(document)
    db.flush()

    for line in payload.lines:
        item = _get_item_by_sku(db, line.sku)
        counted = quantize_qty(line.counted_qty)
        on_hand, _, _ = _position_totals(db, item.id, location.id)
        variance = quantize_qty(counted - on_hand)

        doc_line = InventoryDocumentLine(
            document_id=document.id,
            item_id=item.id,
            quantity=counted,
            batch_no=line.batch_no,
            expiry_date=line.expiry_date,
            note=None,
        )
        db.add(doc_line)
        db.flush()

        db.add(
            InventoryLedger(
                item_id=item.id,
                location_id=location.id,
                store_id=location.store_id,
                entry_type="count_adjustment",
                quantity_delta=variance,
                reservation_delta=Decimal("0"),
                document_id=document.id,
                document_line_id=doc_line.id,
                batch_no=line.batch_no,
                expiry_date=line.expiry_date,
            )
        )

    audit_event(
        db,
        action="inventory.count.posted",
        resource_type="inventory_document",
        resource_id=str(document.id),
        actor_user_id=current_user.id,
        detail={"location": location.code, "line_count": len(payload.lines)},
    )

    return InventoryDocumentResponse(document_id=document.id, doc_type=document.doc_type, status=document.status)


def create_reservation(db: Session, payload: ReservationCreateRequest, current_user: AuthUser) -> ReservationResponse:
    item = _get_item_by_sku(db, payload.sku)
    location = _get_location_by_code(db, payload.location_code, store_id=current_user.store_id)
    qty = quantize_qty(payload.quantity)
    actor_user_id = db.execute(select(User.id).where(User.id == current_user.id)).scalar_one_or_none()

    # Lock open reservations for this position before evaluating availability.
    db.execute(
        select(InventoryReservation.id)
        .where(
            InventoryReservation.item_id == item.id,
            InventoryReservation.location_id == location.id,
            InventoryReservation.status.in_(["open", "partial"]),
        )
        .with_for_update()
    ).all()

    # Lock position ledger rows so concurrent reservations on the same item/location serialize.
    db.execute(
        select(InventoryLedger.id)
        .where(
            InventoryLedger.item_id == item.id,
            InventoryLedger.location_id == location.id,
        )
        .with_for_update()
    ).all()

    _, _, available = _position_totals(db, item.id, location.id)
    if available < qty:
        raise InventoryError(f"Insufficient available stock for SKU {item.sku}")

    reservation = InventoryReservation(
        order_reference=payload.order_reference.strip(),
        item_id=item.id,
        location_id=location.id,
        store_id=location.store_id,
        reserved_qty=qty,
        released_qty=Decimal("0"),
        status="open",
        created_by_user_id=actor_user_id,
    )
    db.add(reservation)
    db.flush()

    db.add(
        InventoryLedger(
            item_id=item.id,
            location_id=location.id,
            store_id=location.store_id,
            entry_type="reservation_create",
            quantity_delta=Decimal("0"),
            reservation_delta=qty,
            reservation_id=reservation.id,
            order_reference=reservation.order_reference,
        )
    )

    audit_event(
        db,
        action="inventory.reservation.created",
        resource_type="inventory_reservation",
        resource_id=str(reservation.id),
        actor_user_id=actor_user_id,
        detail={"order_reference": reservation.order_reference, "sku": item.sku, "qty": str(qty)},
    )

    logger.info(
        "inventory_reservation_created",
        extra=mask_record(
            {
                "reservation_id": reservation.id,
                "order_reference": reservation.order_reference,
                "sku": item.sku,
                "location_code": location.code,
                "reserved_qty": str(qty),
                "operator_user_id": actor_user_id,
            },
            _SENSITIVE_LOG_KEYS,
        ),
    )

    return ReservationResponse(
        id=reservation.id,
        order_reference=reservation.order_reference,
        sku=item.sku,
        location_code=location.code,
        reserved_qty=reservation.reserved_qty,
        released_qty=reservation.released_qty,
        status=reservation.status,
    )


def release_reservation(db: Session, payload: ReservationReleaseRequest, current_user: AuthUser) -> ReservationResponse:
    reservation = db.execute(
        select(InventoryReservation).where(InventoryReservation.id == payload.reservation_id).with_for_update()
    ).scalar_one_or_none()
    if not reservation:
        raise InventoryError("Reservation not found")

    item = db.execute(select(InventoryItem).where(InventoryItem.id == reservation.item_id)).scalar_one()
    location = db.execute(select(InventoryLocation).where(InventoryLocation.id == reservation.location_id)).scalar_one()
    if current_user.store_id is not None and reservation.store_id != current_user.store_id:
        raise InventoryError("Reservation not found")

    remaining = quantize_qty(Decimal(reservation.reserved_qty) - Decimal(reservation.released_qty))
    if remaining > Decimal("0"):
        reservation.released_qty = quantize_qty(Decimal(reservation.released_qty) + remaining)
        reservation.status = "released"
        reservation.released_by_user_id = current_user.id

        db.add(
            InventoryLedger(
                item_id=reservation.item_id,
                location_id=reservation.location_id,
                store_id=location.store_id,
                entry_type="reservation_release",
                quantity_delta=Decimal("0"),
                reservation_delta=-remaining,
                reservation_id=reservation.id,
                order_reference=reservation.order_reference,
            )
        )

        audit_event(
            db,
            action="inventory.reservation.released",
            resource_type="inventory_reservation",
            resource_id=str(reservation.id),
            actor_user_id=current_user.id,
            detail={"order_reference": reservation.order_reference, "sku": item.sku, "released_qty": str(remaining)},
        )

        logger.info(
            "inventory_reservation_released",
            extra=mask_record(
                {
                    "reservation_id": reservation.id,
                    "order_reference": reservation.order_reference,
                    "sku": item.sku,
                    "location_code": location.code,
                    "released_qty": str(remaining),
                    "operator_user_id": current_user.id,
                },
                _SENSITIVE_LOG_KEYS,
            ),
        )

    return ReservationResponse(
        id=reservation.id,
        order_reference=reservation.order_reference,
        sku=item.sku,
        location_code=location.code,
        reserved_qty=reservation.reserved_qty,
        released_qty=reservation.released_qty,
        status=reservation.status,
    )


def list_positions(
    db: Session,
    sku: str | None,
    location_code: str | None,
    store_id: int | None,
) -> list[InventoryPositionResponse]:
    conditions = []
    if sku:
        item = _get_item_by_sku(db, sku)
        conditions.append(InventoryLedger.item_id == item.id)
    if location_code:
        location = _get_location_by_code(db, location_code, store_id=store_id)
        conditions.append(InventoryLedger.location_id == location.id)
    if store_id is not None:
        conditions.append(InventoryLedger.store_id == store_id)

    rows = db.execute(
        select(InventoryLedger.item_id, InventoryLedger.location_id)
        .where(*conditions)
        .group_by(InventoryLedger.item_id, InventoryLedger.location_id)
        .order_by(InventoryLedger.item_id.asc(), InventoryLedger.location_id.asc())
    ).all()

    responses: list[InventoryPositionResponse] = []
    for item_id, loc_id in rows:
        item = db.execute(select(InventoryItem).where(InventoryItem.id == item_id)).scalar_one()
        location = db.execute(select(InventoryLocation).where(InventoryLocation.id == loc_id)).scalar_one()
        responses.append(_position_response(db, item, location))
    return responses


def get_position(db: Session, sku: str, location_code: str, store_id: int | None) -> InventoryPositionResponse:
    item = _get_item_by_sku(db, sku)
    location = _get_location_by_code(db, location_code, store_id=store_id)
    return _position_response(db, item, location)


def list_ledger_entries(db: Session, limit: int = 200, store_id: int | None = None) -> list[InventoryLedgerEntryResponse]:
    stmt = select(InventoryLedger).order_by(InventoryLedger.id.desc()).limit(limit)
    if store_id is not None:
        stmt = stmt.where(InventoryLedger.store_id == store_id)
    rows = db.execute(stmt).scalars().all()
    responses: list[InventoryLedgerEntryResponse] = []
    for row in rows:
        item = db.execute(select(InventoryItem).where(InventoryItem.id == row.item_id)).scalar_one()
        location = db.execute(select(InventoryLocation).where(InventoryLocation.id == row.location_id)).scalar_one()
        responses.append(
            InventoryLedgerEntryResponse(
                id=row.id,
                sku=item.sku,
                location_code=location.code,
                entry_type=row.entry_type,
                quantity_delta=row.quantity_delta,
                reservation_delta=row.reservation_delta,
                order_reference=row.order_reference,
            )
        )
    return responses
