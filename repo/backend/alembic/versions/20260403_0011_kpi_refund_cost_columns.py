"""add refund_total and cost_total to kpi_daily_metrics

Revision ID: 20260403_0011
Revises: 20260328_0010
Create Date: 2026-04-03 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260403_0011"
down_revision: str | None = "20260328_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kpi_daily_metrics",
        sa.Column("refund_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "kpi_daily_metrics",
        sa.Column("cost_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("kpi_daily_metrics", "cost_total")
    op.drop_column("kpi_daily_metrics", "refund_total")
