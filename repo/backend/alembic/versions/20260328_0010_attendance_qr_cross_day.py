"""add attendance qr single-use and cross-day rule support

Revision ID: 20260328_0010
Revises: 20260328_0009
Create Date: 2026-03-28 11:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260328_0010"
down_revision: str | None = "20260328_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attendance_rule_configs",
        sa.Column("cross_day_shift_cutoff_hour", sa.Integer(), nullable=False, server_default="6"),
    )
    op.add_column("rotating_qr_tokens", sa.Column("used_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_rotating_qr_tokens_used_at"), "rotating_qr_tokens", ["used_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rotating_qr_tokens_used_at"), table_name="rotating_qr_tokens")
    op.drop_column("rotating_qr_tokens", "used_at")
    op.drop_column("attendance_rule_configs", "cross_day_shift_cutoff_hour")
