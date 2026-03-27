from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_roles
from app.core.errors import bad_request
from app.db.session import get_db
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
from app.services.inventory_service import (
    InventoryError,
    create_item,
    create_location,
    create_reservation,
    get_position,
    list_ledger_entries,
    list_positions,
    post_count,
    post_receiving,
    post_transfer,
    release_reservation,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])

_INVENTORY_ROLES = {"administrator", "store_manager", "inventory_clerk"}


@router.post("/items", response_model=InventoryItemResponse)
def inventory_create_item(
    payload: InventoryItemCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryItemResponse:
    try:
        result = create_item(db, payload, current_user)
        db.commit()
        return result
    except InventoryError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/locations", response_model=InventoryLocationResponse)
def inventory_create_location(
    payload: InventoryLocationCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryLocationResponse:
    try:
        result = create_location(db, payload, current_user)
        db.commit()
        return result
    except InventoryError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/receiving", response_model=InventoryDocumentResponse)
def inventory_receiving(
    payload: ReceivingRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryDocumentResponse:
    try:
        result = post_receiving(db, payload, current_user)
        db.commit()
        return result
    except InventoryError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/transfers", response_model=InventoryDocumentResponse)
def inventory_transfer(
    payload: TransferRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryDocumentResponse:
    try:
        result = post_transfer(db, payload, current_user)
        db.commit()
        return result
    except InventoryError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/counts", response_model=InventoryDocumentResponse)
def inventory_count(
    payload: CountRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryDocumentResponse:
    try:
        result = post_count(db, payload, current_user)
        db.commit()
        return result
    except InventoryError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/reservations", response_model=ReservationResponse)
def inventory_create_reservation(
    payload: ReservationCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES)),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    try:
        result = create_reservation(db, payload, current_user)
        db.commit()
        return result
    except InventoryError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.post("/reservations/release", response_model=ReservationResponse)
def inventory_release_reservation(
    payload: ReservationReleaseRequest,
    current_user: AuthUser = Depends(get_current_user),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES)),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    try:
        result = release_reservation(db, payload, current_user)
        db.commit()
        return result
    except InventoryError as exc:
        db.rollback()
        raise bad_request(str(exc))


@router.get("/positions", response_model=list[InventoryPositionResponse])
def inventory_positions(
    sku: str | None = Query(default=None),
    location_code: str | None = Query(default=None),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES | {"cashier"})),
    db: Session = Depends(get_db),
) -> list[InventoryPositionResponse]:
    try:
        return list_positions(db, sku, location_code)
    except InventoryError as exc:
        raise bad_request(str(exc))


@router.get("/positions/{sku}/{location_code}", response_model=InventoryPositionResponse)
def inventory_position(
    sku: str,
    location_code: str,
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES | {"cashier"})),
    db: Session = Depends(get_db),
) -> InventoryPositionResponse:
    try:
        return get_position(db, sku, location_code)
    except InventoryError as exc:
        raise bad_request(str(exc))


@router.get("/ledger", response_model=list[InventoryLedgerEntryResponse])
def inventory_ledger(
    limit: int = Query(default=200, ge=1, le=1000),
    _: AuthUser = Depends(require_roles(_INVENTORY_ROLES | {"cashier"})),
    db: Session = Depends(get_db),
) -> list[InventoryLedgerEntryResponse]:
    return list_ledger_entries(db, limit=limit)
