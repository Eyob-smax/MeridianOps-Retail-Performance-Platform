from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DashboardAuditEntry(BaseModel):
    id: int
    action: str
    resource_type: str
    resource_id: str
    actor_user_id: int | None
    detail_json: str
    created_at: str


class DashboardAuditFeedResponse(BaseModel):
    entries: list[DashboardAuditEntry]


class ExportMetadataResponse(BaseModel):
    filename: str
    content_type: str
    size_bytes: int


class DrillDownResponse(BaseModel):
    dashboard_id: int
    store_id: int
    store_name: str
    start_date: date
    end_date: date
    orders: int
    revenue: Decimal
    refunds: Decimal
    cost: Decimal
    gross_margin: Decimal


class DateDrillDownResponse(BaseModel):
    dashboard_id: int
    business_date: date
    start_date: date
    end_date: date
    orders: int
    revenue: Decimal
    refunds: Decimal
    cost: Decimal
    gross_margin: Decimal
