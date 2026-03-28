from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class AttendanceRuleResponse(BaseModel):
    tolerance_minutes: int
    auto_break_after_hours: int
    auto_break_minutes: int
    cross_day_shift_cutoff_hour: int
    late_early_penalty_hours: str


class AttendanceRuleUpdateRequest(BaseModel):
    tolerance_minutes: int = Field(ge=0, le=120)
    auto_break_after_hours: int = Field(ge=1, le=24)
    auto_break_minutes: int = Field(ge=0, le=180)
    cross_day_shift_cutoff_hour: int = Field(ge=0, le=23)
    late_early_penalty_hours: Decimal = Field(ge=Decimal("0"), le=Decimal("8"))


class RotatingQRTokenResponse(BaseModel):
    token: str
    expires_at: datetime


class CheckInRequest(BaseModel):
    device_id: str = Field(min_length=2, max_length=120)
    qr_token: str | None = Field(default=None, min_length=10, max_length=120)
    nfc_tag: str | None = Field(default=None, min_length=6, max_length=120)
    check_in_at: datetime | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    @model_validator(mode="after")
    def validate_auth_factors(self):
        if not self.qr_token and not self.nfc_tag:
            raise ValueError("Either qr_token or nfc_tag is required")
        return self


class CheckOutRequest(BaseModel):
    device_id: str = Field(min_length=2, max_length=120)
    qr_token: str | None = Field(default=None, min_length=10, max_length=120)
    nfc_tag: str | None = Field(default=None, min_length=6, max_length=120)
    check_out_at: datetime | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    @model_validator(mode="after")
    def validate_auth_factors(self):
        if not self.qr_token and not self.nfc_tag:
            raise ValueError("Either qr_token or nfc_tag is required")
        return self


class AttendanceShiftResponse(BaseModel):
    id: int
    user_id: int
    check_in_at: datetime
    check_out_at: datetime | None
    status: str
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None


class AttendanceDailyResultResponse(BaseModel):
    id: int
    user_id: int
    business_date: date
    worked_hours: str
    auto_break_minutes: int
    late_incidents: int
    early_incidents: int
    penalty_hours: str


class CheckOutResponse(BaseModel):
    shift: AttendanceShiftResponse
    daily_result: AttendanceDailyResultResponse


class MakeupRequestCreate(BaseModel):
    business_date: date
    reason: str = Field(min_length=5)


class MakeupRequestApprove(BaseModel):
    manager_note: str = Field(min_length=2)


class MakeupRequestResponse(BaseModel):
    id: int
    user_id: int
    business_date: date
    reason: str
    status: str
    manager_note: str | None
    manager_user_id: int | None
    created_at: datetime
    reviewed_at: datetime | None
