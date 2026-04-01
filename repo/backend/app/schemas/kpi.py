from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class KPIJobRunResponse(BaseModel):
    id: int
    job_name: str
    trigger_type: str
    status: str
    scheduled_for: datetime | None
    started_at: datetime
    finished_at: datetime | None
    attempts_made: int
    max_attempts: int
    processed_from_date: date
    processed_to_date: date
    records_written: int
    error_message: str | None


class KPIDailyMetricResponse(BaseModel):
    id: int
    business_date: date
    store_id: int
    conversion_rate: str
    average_order_value: str
    inventory_turnover: str
    total_attempts: int
    successful_orders: int
    revenue_total: str
    inventory_outbound_qty: str
    average_inventory_qty: str


class KPIBackfillRequest(BaseModel):
    start_date: date
    end_date: date
    store_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class KPIBackfillResponse(BaseModel):
    run_id: int
    status: str
    processed_from_date: date
    processed_to_date: date
    records_written: int


class SeedDataResponse(BaseModel):
    created_members: int
    created_campaigns: int
    created_coupons: int
    created_inventory_items: int
    created_inventory_ledger_rows: int
    created_training_topics: int
    created_training_questions: int
    created_training_assignments: int
    created_training_states: int
    created_training_snapshots: int
    created_dashboard_layouts: int


class SchedulerStatusResponse(BaseModel):
    job_name: str
    enabled: bool
    next_run_at: datetime | None
    last_run_status: str | None
    last_run_at: datetime | None
