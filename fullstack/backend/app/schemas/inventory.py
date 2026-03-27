from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class InventoryItemCreateRequest(BaseModel):
    sku: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=120)
    unit: str = Field(default="ea", min_length=1, max_length=20)
    batch_tracking_enabled: bool = False
    expiry_tracking_enabled: bool = False


class InventoryLocationCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=120)


class InventoryItemResponse(BaseModel):
    id: int
    sku: str
    name: str
    unit: str
    batch_tracking_enabled: bool
    expiry_tracking_enabled: bool


class InventoryLocationResponse(BaseModel):
    id: int
    code: str
    name: str


class InventoryDocumentLineInput(BaseModel):
    sku: str = Field(min_length=2, max_length=60)
    quantity: Decimal = Field(gt=Decimal("0"))
    batch_no: str | None = Field(default=None, max_length=60)
    expiry_date: date | None = None
    note: str | None = Field(default=None, max_length=255)


class ReceivingRequest(BaseModel):
    location_code: str
    note: str | None = Field(default=None, max_length=255)
    lines: list[InventoryDocumentLineInput]


class TransferRequest(BaseModel):
    source_location_code: str
    target_location_code: str
    note: str | None = Field(default=None, max_length=255)
    lines: list[InventoryDocumentLineInput]


class CountLineInput(BaseModel):
    sku: str
    counted_qty: Decimal = Field(ge=Decimal("0"))
    batch_no: str | None = Field(default=None, max_length=60)
    expiry_date: date | None = None


class CountRequest(BaseModel):
    location_code: str
    note: str | None = Field(default=None, max_length=255)
    lines: list[CountLineInput]


class ReservationCreateRequest(BaseModel):
    order_reference: str = Field(min_length=1, max_length=60)
    sku: str
    location_code: str
    quantity: Decimal = Field(gt=Decimal("0"))


class ReservationReleaseRequest(BaseModel):
    reservation_id: int


class InventoryPositionResponse(BaseModel):
    sku: str
    item_name: str
    location_code: str
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal


class InventoryDocumentResponse(BaseModel):
    document_id: int
    doc_type: str
    status: str


class ReservationResponse(BaseModel):
    id: int
    order_reference: str
    sku: str
    location_code: str
    reserved_qty: Decimal
    released_qty: Decimal
    status: str


class InventoryLedgerEntryResponse(BaseModel):
    id: int
    sku: str
    location_code: str
    entry_type: str
    quantity_delta: Decimal
    reservation_delta: Decimal
    order_reference: str | None


class InventoryWorkflowResponse(BaseModel):
    document: InventoryDocumentResponse | None = None
    reservation: ReservationResponse | None = None
    position: InventoryPositionResponse | None = None
