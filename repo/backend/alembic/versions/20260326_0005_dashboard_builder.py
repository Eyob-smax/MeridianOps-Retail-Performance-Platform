"""add analytics dashboards, share links, and audit surfaces

Revision ID: 20260326_0005
Revises: 20260326_0004
Create Date: 2026-03-26 19:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260326_0005"
down_revision: str | None = "20260326_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dashboard_layouts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("layout_json", sa.Text(), nullable=False),
        sa.Column("allowed_store_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("default_start_date", sa.Date(), nullable=True),
        sa.Column("default_end_date", sa.Date(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dashboard_layouts_name"), "dashboard_layouts", ["name"], unique=False)

    op.create_table(
        "dashboard_share_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dashboard_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=80), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("allowed_store_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("readonly", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dashboard_id"], ["dashboard_layouts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_dashboard_share_links_dashboard_id"),
        "dashboard_share_links",
        ["dashboard_id"],
        unique=False,
    )
    op.create_index(op.f("ix_dashboard_share_links_token"), "dashboard_share_links", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_dashboard_share_links_token"), table_name="dashboard_share_links")
    op.drop_index(op.f("ix_dashboard_share_links_dashboard_id"), table_name="dashboard_share_links")
    op.drop_table("dashboard_share_links")

    op.drop_index(op.f("ix_dashboard_layouts_name"), table_name="dashboard_layouts")
    op.drop_table("dashboard_layouts")
