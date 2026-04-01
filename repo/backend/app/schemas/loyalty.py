from decimal import Decimal

from pydantic import BaseModel, Field

from app.types.business import MemberTier


class MemberCreateRequest(BaseModel):
    member_code: str = Field(min_length=2, max_length=40)
    full_name: str = Field(min_length=2, max_length=120)
    tier: MemberTier = MemberTier.BASE
    stored_value_enabled: bool = False


class MemberUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    tier: MemberTier | None = None
    stored_value_enabled: bool | None = None


class MemberResponse(BaseModel):
    id: int
    store_id: int | None = None
    member_code: str
    full_name: str
    tier: MemberTier
    stored_value_enabled: bool
    points_balance: int
    wallet_balance: Decimal | None


class PointsAccrualRequest(BaseModel):
    pre_tax_amount: Decimal = Field(gt=Decimal("0"))
    reason: str = Field(default="purchase", min_length=2, max_length=120)


class PointsAdjustmentRequest(BaseModel):
    points_delta: int
    reason: str = Field(min_length=2, max_length=120)


class WalletMutationRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"))
    reason: str = Field(min_length=2, max_length=120)


class PointsLedgerEntry(BaseModel):
    id: int
    member_id: int
    points_delta: int
    reason: str
    pre_tax_amount: Decimal | None


class WalletLedgerEntry(BaseModel):
    id: int
    member_id: int
    entry_type: str
    amount: Decimal
    balance_after: Decimal
    reason: str
