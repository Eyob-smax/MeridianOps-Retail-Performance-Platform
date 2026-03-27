from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttendanceRuleConfig(Base):
    __tablename__ = "attendance_rule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tolerance_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    auto_break_after_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    auto_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    late_early_penalty_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0.25"))
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DeviceBinding(Base):
    __tablename__ = "device_bindings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_device_bindings_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RotatingQRToken(Base):
    __tablename__ = "rotating_qr_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AttendanceShift(Base):
    __tablename__ = "attendance_shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_binding_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_bindings.id", ondelete="SET NULL"), nullable=True
    )
    qr_token_id: Mapped[int | None] = mapped_column(ForeignKey("rotating_qr_tokens.id", ondelete="SET NULL"), nullable=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    check_in_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    check_out_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    check_out_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)


class AttendanceDailyResult(Base):
    __tablename__ = "attendance_daily_results"
    __table_args__ = (UniqueConstraint("user_id", "business_date", name="uq_attendance_daily_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("attendance_shifts.id", ondelete="CASCADE"), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    worked_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    auto_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    late_incidents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_incidents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    penalty_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AttendanceMakeupRequest(Base):
    __tablename__ = "attendance_makeup_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    manager_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
