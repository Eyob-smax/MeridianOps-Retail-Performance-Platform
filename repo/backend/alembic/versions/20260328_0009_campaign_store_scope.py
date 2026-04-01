"""add campaign store scoping

Revision ID: 20260328_0009
Revises: 20260327_0008
Create Date: 2026-03-28 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260328_0009"
down_revision: str | None = "20260327_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_campaigns_store_id"), "campaigns", ["store_id"], unique=False)

    op.add_column("coupons", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_coupons_store_id"), "coupons", ["store_id"], unique=False)

    op.add_column("coupon_issuance_events", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_coupon_issuance_events_store_id"), "coupon_issuance_events", ["store_id"], unique=False)

    op.add_column("coupon_redemption_events", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_coupon_redemption_events_store_id"), "coupon_redemption_events", ["store_id"], unique=False)

    op.execute(
        """
        UPDATE campaigns
        SET store_id = (
            SELECT users.store_id
            FROM users
            WHERE users.id = campaigns.created_by_user_id
        )
        WHERE campaigns.store_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE coupons
        SET store_id = (
            SELECT campaigns.store_id
            FROM campaigns
            WHERE campaigns.id = coupons.campaign_id
        )
        WHERE coupons.store_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE coupon_issuance_events
        SET store_id = (
            SELECT campaigns.store_id
            FROM campaigns
            WHERE campaigns.id = coupon_issuance_events.campaign_id
        )
        WHERE coupon_issuance_events.store_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE coupon_redemption_events
        SET store_id = (
            SELECT campaigns.store_id
            FROM campaigns
            WHERE campaigns.id = coupon_redemption_events.campaign_id
        )
        WHERE coupon_redemption_events.store_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_coupon_redemption_events_store_id"), table_name="coupon_redemption_events")
    op.drop_column("coupon_redemption_events", "store_id")

    op.drop_index(op.f("ix_coupon_issuance_events_store_id"), table_name="coupon_issuance_events")
    op.drop_column("coupon_issuance_events", "store_id")

    op.drop_index(op.f("ix_coupons_store_id"), table_name="coupons")
    op.drop_column("coupons", "store_id")

    op.drop_index(op.f("ix_campaigns_store_id"), table_name="campaigns")
    op.drop_column("campaigns", "store_id")
