from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    percent_off: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    fixed_amount_off: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    threshold_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    effective_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    daily_redemption_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    per_member_daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    coupon_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    issuance_method: Mapped[str] = mapped_column(String(30), nullable=False)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True)
    issued_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    order_reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    redemption_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )


class CouponIssuanceEvent(Base):
    __tablename__ = "coupon_issuance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    operator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    qr_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CouponRedemptionEvent(Base):
    __tablename__ = "coupon_redemption_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True, index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    order_reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pre_tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
