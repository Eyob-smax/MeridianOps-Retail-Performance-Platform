"""add kpi scheduler and materialized tables

Revision ID: 20260326_0006
Revises: 20260326_0005
Create Date: 2026-03-26 21:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260326_0006"
down_revision: str | None = "20260326_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kpi_job_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_name", sa.String(length=80), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("processed_from_date", sa.Date(), nullable=False),
        sa.Column("processed_to_date", sa.Date(), nullable=False),
        sa.Column("records_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kpi_job_runs_job_name"), "kpi_job_runs", ["job_name"], unique=False)
    op.create_index(op.f("ix_kpi_job_runs_trigger_type"), "kpi_job_runs", ["trigger_type"], unique=False)
    op.create_index(op.f("ix_kpi_job_runs_status"), "kpi_job_runs", ["status"], unique=False)

    op.create_table(
        "kpi_daily_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversion_rate", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("average_order_value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("inventory_turnover", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("total_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revenue_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("inventory_outbound_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("average_inventory_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["kpi_job_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_date", "store_id", name="uq_kpi_daily_metrics_date_store"),
    )
    op.create_index(op.f("ix_kpi_daily_metrics_business_date"), "kpi_daily_metrics", ["business_date"], unique=False)
    op.create_index(op.f("ix_kpi_daily_metrics_store_id"), "kpi_daily_metrics", ["store_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_kpi_daily_metrics_store_id"), table_name="kpi_daily_metrics")
    op.drop_index(op.f("ix_kpi_daily_metrics_business_date"), table_name="kpi_daily_metrics")
    op.drop_table("kpi_daily_metrics")

    op.drop_index(op.f("ix_kpi_job_runs_status"), table_name="kpi_job_runs")
    op.drop_index(op.f("ix_kpi_job_runs_trigger_type"), table_name="kpi_job_runs")
    op.drop_index(op.f("ix_kpi_job_runs_job_name"), table_name="kpi_job_runs")
    op.drop_table("kpi_job_runs")
