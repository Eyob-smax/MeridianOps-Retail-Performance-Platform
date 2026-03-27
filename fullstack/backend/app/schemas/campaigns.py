from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.types.business import CampaignType, IssuanceMethod


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    campaign_type: CampaignType
    effective_start: date
    effective_end: date
    daily_redemption_cap: int = Field(default=200, ge=1)
    per_member_daily_limit: int = Field(default=1, ge=1)
    percent_off: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("1"))
    fixed_amount_off: Decimal | None = Field(default=None, gt=Decimal("0"))
    threshold_amount: Decimal | None = Field(default=None, gt=Decimal("0"))


class CampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    effective_start: date | None = None
    effective_end: date | None = None
    daily_redemption_cap: int | None = Field(default=None, ge=1)
    per_member_daily_limit: int | None = Field(default=None, ge=1)
    percent_off: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("1"))
    fixed_amount_off: Decimal | None = Field(default=None, gt=Decimal("0"))
    threshold_amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    is_active: bool | None = None


class CampaignResponse(BaseModel):
    id: int
    name: str
    campaign_type: CampaignType
    effective_start: date
    effective_end: date
    daily_redemption_cap: int
    per_member_daily_limit: int
    is_active: bool
    percent_off: Decimal | None
    fixed_amount_off: Decimal | None
    threshold_amount: Decimal | None


class CouponIssueRequest(BaseModel):
    campaign_id: int
    issuance_method: IssuanceMethod
    member_code: str | None = None


class CouponIssueResponse(BaseModel):
    coupon_code: str
    campaign_id: int
    issuance_method: IssuanceMethod
    qr_payload: str | None = None


class CouponRedeemRequest(BaseModel):
    coupon_code: str
    member_code: str | None = None
    pre_tax_amount: Decimal = Field(gt=Decimal("0"))
    order_reference: str = Field(min_length=1, max_length=60)


class CouponRedeemResponse(BaseModel):
    success: bool
    reason_code: str
    message: str
    discount_amount: Decimal = Decimal("0.00")
    final_amount: Decimal
    campaign_id: int | None = None
