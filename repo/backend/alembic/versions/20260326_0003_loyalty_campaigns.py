"""add loyalty and campaign foundations

Revision ID: 20260326_0003
Revises: 20260326_0002
Create Date: 2026-03-26 17:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260326_0003"
down_revision: str | None = "20260326_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_code", sa.String(length=40), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False, server_default="base"),
        sa.Column("stored_value_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_code"),
    )
    op.create_index(op.f("ix_members_member_code"), "members", ["member_code"], unique=True)
    op.create_index(op.f("ix_members_tier"), "members", ["tier"], unique=False)

    op.create_table(
        "points_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("points_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("pre_tax_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_points_ledger_member_id"), "points_ledger", ["member_id"], unique=False)

    op.create_table(
        "wallet_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id"),
    )
    op.create_index(op.f("ix_wallet_accounts_member_id"), "wallet_accounts", ["member_id"], unique=True)

    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_account_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["wallet_account_id"], ["wallet_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wallet_ledger_wallet_account_id"), "wallet_ledger", ["wallet_account_id"], unique=False)
    op.create_index(op.f("ix_wallet_ledger_member_id"), "wallet_ledger", ["member_id"], unique=False)

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("campaign_type", sa.String(length=30), nullable=False),
        sa.Column("percent_off", sa.Numeric(7, 4), nullable=True),
        sa.Column("fixed_amount_off", sa.Numeric(12, 2), nullable=True),
        sa.Column("threshold_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("effective_start", sa.Date(), nullable=False),
        sa.Column("effective_end", sa.Date(), nullable=False),
        sa.Column("daily_redemption_cap", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("per_member_daily_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaigns_campaign_type"), "campaigns", ["campaign_type"], unique=False)
    op.create_index(op.f("ix_campaigns_effective_start"), "campaigns", ["effective_start"], unique=False)
    op.create_index(op.f("ix_campaigns_effective_end"), "campaigns", ["effective_end"], unique=False)

    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("coupon_code", sa.String(length=64), nullable=False),
        sa.Column("issuance_method", sa.String(length=30), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("order_reference", sa.String(length=60), nullable=True),
        sa.Column("redemption_member_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["redeemed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["redemption_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("coupon_code"),
    )
    op.create_index(op.f("ix_coupons_campaign_id"), "coupons", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_coupons_coupon_code"), "coupons", ["coupon_code"], unique=True)
    op.create_index(op.f("ix_coupons_member_id"), "coupons", ["member_id"], unique=False)

    op.create_table(
        "coupon_issuance_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coupon_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("qr_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coupon_issuance_events_coupon_id"), "coupon_issuance_events", ["coupon_id"], unique=False)
    op.create_index(op.f("ix_coupon_issuance_events_campaign_id"), "coupon_issuance_events", ["campaign_id"], unique=False)

    op.create_table(
        "coupon_redemption_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coupon_id", sa.Integer(), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("order_reference", sa.String(length=60), nullable=True),
        sa.Column("pre_tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coupon_redemption_events_coupon_id"), "coupon_redemption_events", ["coupon_id"], unique=False)
    op.create_index(op.f("ix_coupon_redemption_events_campaign_id"), "coupon_redemption_events", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_coupon_redemption_events_member_id"), "coupon_redemption_events", ["member_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_resource_type"), "audit_log", ["resource_type"], unique=False)
    op.create_index(op.f("ix_audit_log_resource_id"), "audit_log", ["resource_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_resource_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_resource_type"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_action"), table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index(op.f("ix_coupon_redemption_events_member_id"), table_name="coupon_redemption_events")
    op.drop_index(op.f("ix_coupon_redemption_events_campaign_id"), table_name="coupon_redemption_events")
    op.drop_index(op.f("ix_coupon_redemption_events_coupon_id"), table_name="coupon_redemption_events")
    op.drop_table("coupon_redemption_events")

    op.drop_index(op.f("ix_coupon_issuance_events_campaign_id"), table_name="coupon_issuance_events")
    op.drop_index(op.f("ix_coupon_issuance_events_coupon_id"), table_name="coupon_issuance_events")
    op.drop_table("coupon_issuance_events")

    op.drop_index(op.f("ix_coupons_member_id"), table_name="coupons")
    op.drop_index(op.f("ix_coupons_coupon_code"), table_name="coupons")
    op.drop_index(op.f("ix_coupons_campaign_id"), table_name="coupons")
    op.drop_table("coupons")

    op.drop_index(op.f("ix_campaigns_effective_end"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_effective_start"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_campaign_type"), table_name="campaigns")
    op.drop_table("campaigns")

    op.drop_index(op.f("ix_wallet_ledger_member_id"), table_name="wallet_ledger")
    op.drop_index(op.f("ix_wallet_ledger_wallet_account_id"), table_name="wallet_ledger")
    op.drop_table("wallet_ledger")

    op.drop_index(op.f("ix_wallet_accounts_member_id"), table_name="wallet_accounts")
    op.drop_table("wallet_accounts")

    op.drop_index(op.f("ix_points_ledger_member_id"), table_name="points_ledger")
    op.drop_table("points_ledger")

    op.drop_index(op.f("ix_members_tier"), table_name="members")
    op.drop_index(op.f("ix_members_member_code"), table_name="members")
    op.drop_table("members")
