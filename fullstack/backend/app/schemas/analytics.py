from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

WidgetKind = Literal["kpi", "trend", "breakdown", "table"]
WidgetMetric = Literal["revenue", "orders", "refunds", "gross_margin"]
WidgetDimension = Literal["store", "date"]
ExportFormat = Literal["csv", "png", "pdf"]


class DashboardWidget(BaseModel):
    id: str = Field(min_length=2, max_length=64)
    kind: WidgetKind
    title: str = Field(min_length=2, max_length=120)
    metric: WidgetMetric
    dimension: WidgetDimension | None = None
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0, le=999)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=12)

    @model_validator(mode="after")
    def validate_grid_span(self):
        if self.x + self.w > 12:
            raise ValueError("Widget width overflows 12-column grid")
        return self


class DashboardCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    widgets: list[DashboardWidget] = Field(min_length=1, max_length=24)
    allowed_store_ids: list[int] = Field(default_factory=list)
    default_start_date: date | None = None
    default_end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.default_start_date and self.default_end_date and self.default_end_date < self.default_start_date:
            raise ValueError("default_end_date must be on or after default_start_date")
        return self


class DashboardUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    widgets: list[DashboardWidget] | None = Field(default=None, min_length=1, max_length=24)
    allowed_store_ids: list[int] | None = None
    default_start_date: date | None = None
    default_end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.default_start_date and self.default_end_date and self.default_end_date < self.default_start_date:
            raise ValueError("default_end_date must be on or after default_start_date")
        return self


class StoreOption(BaseModel):
    id: int
    name: str


class DashboardFilters(BaseModel):
    store_ids: list[int]
    start_date: date
    end_date: date


class DashboardDataRow(BaseModel):
    store_id: int
    store_name: str
    business_date: date
    orders: int
    revenue: Decimal
    refunds: Decimal
    cost: Decimal
    gross_margin: Decimal


class DashboardStoreAggregate(BaseModel):
    store_id: int
    store_name: str
    orders: int
    revenue: Decimal
    refunds: Decimal
    cost: Decimal
    gross_margin: Decimal


class DashboardDateAggregate(BaseModel):
    business_date: date
    orders: int
    revenue: Decimal
    refunds: Decimal
    cost: Decimal
    gross_margin: Decimal


class DashboardTotals(BaseModel):
    orders: int
    revenue: Decimal
    refunds: Decimal
    cost: Decimal
    gross_margin: Decimal


class DashboardDataPayload(BaseModel):
    filters: DashboardFilters
    totals: DashboardTotals
    by_store: list[DashboardStoreAggregate]
    by_date: list[DashboardDateAggregate]
    rows: list[DashboardDataRow]


class DashboardSummaryResponse(BaseModel):
    id: int
    name: str
    description: str | None
    widget_count: int
    allowed_store_ids: list[int]
    created_at: datetime
    updated_at: datetime


class DashboardDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None
    widgets: list[DashboardWidget]
    allowed_store_ids: list[int]
    default_start_date: date | None
    default_end_date: date | None
    store_options: list[StoreOption]
    read_only: bool = False
    data: DashboardDataPayload
    created_at: datetime
    updated_at: datetime


class ShareLinkCreateRequest(BaseModel):
    allowed_store_ids: list[int] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ShareLinkResponse(BaseModel):
    id: int
    dashboard_id: int
    token: str
    share_url: str
    readonly: bool
    is_active: bool
    allowed_store_ids: list[int]
    start_date: date | None
    end_date: date | None
    expires_at: datetime | None
    created_at: datetime


class SharedDashboardResponse(BaseModel):
    dashboard_id: int
    token: str
    name: str
    description: str | None
    widgets: list[DashboardWidget]
    allowed_store_ids: list[int]
    store_options: list[StoreOption]
    read_only: bool
    data: DashboardDataPayload
    created_at: datetime
    updated_at: datetime
