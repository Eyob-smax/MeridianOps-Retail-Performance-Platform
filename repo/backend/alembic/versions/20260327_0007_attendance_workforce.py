"""add attendance and anti-fraud tables

Revision ID: 20260327_0007
Revises: 20260326_0006
Create Date: 2026-03-27 10:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260327_0007"
down_revision: str | None = "20260326_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_rule_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tolerance_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("auto_break_after_hours", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("auto_break_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("late_early_penalty_hours", sa.Numeric(6, 2), nullable=False, server_default="0.25"),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "device_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bound_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_device_bindings_user"),
    )
    op.create_index(op.f("ix_device_bindings_device_id"), "device_bindings", ["device_id"], unique=False)

    op.create_table(
        "rotating_qr_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=120), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_rotating_qr_tokens_token"), "rotating_qr_tokens", ["token"], unique=True)
    op.create_index(op.f("ix_rotating_qr_tokens_expires_at"), "rotating_qr_tokens", ["expires_at"], unique=False)

    op.create_table(
        "attendance_shifts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_binding_id", sa.Integer(), nullable=True),
        sa.Column("qr_token_id", sa.Integer(), nullable=True),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_in_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("check_in_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("check_out_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("check_out_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_binding_id"], ["device_bindings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["qr_token_id"], ["rotating_qr_tokens.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attendance_shifts_user_id"), "attendance_shifts", ["user_id"], unique=False)
    op.create_index(op.f("ix_attendance_shifts_check_in_at"), "attendance_shifts", ["check_in_at"], unique=False)
    op.create_index(op.f("ix_attendance_shifts_status"), "attendance_shifts", ["status"], unique=False)

    op.create_table(
        "attendance_daily_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("worked_hours", sa.Numeric(8, 2), nullable=False),
        sa.Column("auto_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("late_incidents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("early_incidents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penalty_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_id"], ["attendance_shifts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "business_date", name="uq_attendance_daily_user_date"),
    )
    op.create_index(
        op.f("ix_attendance_daily_results_user_id"),
        "attendance_daily_results",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attendance_daily_results_business_date"),
        "attendance_daily_results",
        ["business_date"],
        unique=False,
    )

    op.create_table(
        "attendance_makeup_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("manager_note", sa.Text(), nullable=True),
        sa.Column("manager_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manager_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_attendance_makeup_requests_user_id"),
        "attendance_makeup_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attendance_makeup_requests_status"),
        "attendance_makeup_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_attendance_makeup_requests_status"), table_name="attendance_makeup_requests")
    op.drop_index(op.f("ix_attendance_makeup_requests_user_id"), table_name="attendance_makeup_requests")
    op.drop_table("attendance_makeup_requests")

    op.drop_index(op.f("ix_attendance_daily_results_business_date"), table_name="attendance_daily_results")
    op.drop_index(op.f("ix_attendance_daily_results_user_id"), table_name="attendance_daily_results")
    op.drop_table("attendance_daily_results")

    op.drop_index(op.f("ix_attendance_shifts_status"), table_name="attendance_shifts")
    op.drop_index(op.f("ix_attendance_shifts_check_in_at"), table_name="attendance_shifts")
    op.drop_index(op.f("ix_attendance_shifts_user_id"), table_name="attendance_shifts")
    op.drop_table("attendance_shifts")

    op.drop_index(op.f("ix_rotating_qr_tokens_expires_at"), table_name="rotating_qr_tokens")
    op.drop_index(op.f("ix_rotating_qr_tokens_token"), table_name="rotating_qr_tokens")
    op.drop_table("rotating_qr_tokens")

    op.drop_index(op.f("ix_device_bindings_device_id"), table_name="device_bindings")
    op.drop_table("device_bindings")

    op.drop_table("attendance_rule_configs")
