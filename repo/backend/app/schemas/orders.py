from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderLineInput(BaseModel):
    sku: str = Field(min_length=2, max_length=60)
    location_code: str = Field(min_length=1, max_length=40)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_price: Decimal = Field(ge=Decimal("0"), default=Decimal("0.00"))


class OrderCreateRequest(BaseModel):
    order_reference: str = Field(min_length=1, max_length=60)
    lines: list[OrderLineInput] = Field(min_length=1)


class OrderLineResponse(BaseModel):
    id: int
    sku: str
    location_code: str
    quantity: Decimal
    unit_price: Decimal
    reservation_id: int | None


class OrderResponse(BaseModel):
    id: int
    order_reference: str
    status: str
    total_amount: Decimal
    store_id: int | None
    lines: list[OrderLineResponse] = []
    created_at: datetime | None = None


class OrderTransitionRequest(BaseModel):
    order_reference: str = Field(min_length=1, max_length=60)
