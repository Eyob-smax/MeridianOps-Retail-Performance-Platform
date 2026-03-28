"""add store scoping and nfc badges

Revision ID: 20260327_0008
Revises: 20260327_0007
Create Date: 2026-03-27 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260327_0008"
down_revision: str | None = "20260327_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_store_id"), "users", ["store_id"], unique=False)

    op.add_column("members", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_members_store_id"), "members", ["store_id"], unique=False)

    op.add_column("inventory_locations", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_inventory_locations_store_id"), "inventory_locations", ["store_id"], unique=False)

    op.add_column("inventory_documents", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_inventory_documents_store_id"), "inventory_documents", ["store_id"], unique=False)

    op.add_column("inventory_ledger", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_inventory_ledger_store_id"), "inventory_ledger", ["store_id"], unique=False)

    op.add_column("inventory_reservations", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_inventory_reservations_store_id"), "inventory_reservations", ["store_id"], unique=False)

    op.add_column("quiz_topics", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_quiz_topics_store_id"), "quiz_topics", ["store_id"], unique=False)

    op.add_column("quiz_questions", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_quiz_questions_store_id"), "quiz_questions", ["store_id"], unique=False)

    op.add_column("quiz_assignments", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_quiz_assignments_store_id"), "quiz_assignments", ["store_id"], unique=False)

    op.add_column("spaced_repetition_state", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_spaced_repetition_state_store_id"),
        "spaced_repetition_state",
        ["store_id"],
        unique=False,
    )

    op.add_column("quiz_attempts", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_quiz_attempts_store_id"), "quiz_attempts", ["store_id"], unique=False)

    op.add_column("review_queue_snapshots", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_review_queue_snapshots_store_id"),
        "review_queue_snapshots",
        ["store_id"],
        unique=False,
    )

    op.create_table(
        "nfc_badges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bound_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_nfc_badges_user"),
    )
    op.create_index(op.f("ix_nfc_badges_tag_id"), "nfc_badges", ["tag_id"], unique=False)

    op.add_column("attendance_shifts", sa.Column("store_id", sa.Integer(), nullable=True))
    op.add_column("attendance_shifts", sa.Column("nfc_badge_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_attendance_shifts_store_id"), "attendance_shifts", ["store_id"], unique=False)
    op.create_foreign_key(
        "fk_attendance_shifts_nfc_badge_id",
        "attendance_shifts",
        "nfc_badges",
        ["nfc_badge_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("attendance_daily_results", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_attendance_daily_results_store_id"),
        "attendance_daily_results",
        ["store_id"],
        unique=False,
    )

    op.add_column("attendance_makeup_requests", sa.Column("store_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_attendance_makeup_requests_store_id"),
        "attendance_makeup_requests",
        ["store_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_attendance_makeup_requests_store_id"), table_name="attendance_makeup_requests")
    op.drop_column("attendance_makeup_requests", "store_id")

    op.drop_index(op.f("ix_attendance_daily_results_store_id"), table_name="attendance_daily_results")
    op.drop_column("attendance_daily_results", "store_id")

    op.drop_constraint("fk_attendance_shifts_nfc_badge_id", "attendance_shifts", type_="foreignkey")
    op.drop_index(op.f("ix_attendance_shifts_store_id"), table_name="attendance_shifts")
    op.drop_column("attendance_shifts", "nfc_badge_id")
    op.drop_column("attendance_shifts", "store_id")

    op.drop_index(op.f("ix_nfc_badges_tag_id"), table_name="nfc_badges")
    op.drop_table("nfc_badges")

    op.drop_index(op.f("ix_review_queue_snapshots_store_id"), table_name="review_queue_snapshots")
    op.drop_column("review_queue_snapshots", "store_id")

    op.drop_index(op.f("ix_quiz_attempts_store_id"), table_name="quiz_attempts")
    op.drop_column("quiz_attempts", "store_id")

    op.drop_index(op.f("ix_spaced_repetition_state_store_id"), table_name="spaced_repetition_state")
    op.drop_column("spaced_repetition_state", "store_id")

    op.drop_index(op.f("ix_quiz_assignments_store_id"), table_name="quiz_assignments")
    op.drop_column("quiz_assignments", "store_id")

    op.drop_index(op.f("ix_quiz_questions_store_id"), table_name="quiz_questions")
    op.drop_column("quiz_questions", "store_id")

    op.drop_index(op.f("ix_quiz_topics_store_id"), table_name="quiz_topics")
    op.drop_column("quiz_topics", "store_id")

    op.drop_index(op.f("ix_inventory_reservations_store_id"), table_name="inventory_reservations")
    op.drop_column("inventory_reservations", "store_id")

    op.drop_index(op.f("ix_inventory_ledger_store_id"), table_name="inventory_ledger")
    op.drop_column("inventory_ledger", "store_id")

    op.drop_index(op.f("ix_inventory_documents_store_id"), table_name="inventory_documents")
    op.drop_column("inventory_documents", "store_id")

    op.drop_index(op.f("ix_inventory_locations_store_id"), table_name="inventory_locations")
    op.drop_column("inventory_locations", "store_id")

    op.drop_index(op.f("ix_members_store_id"), table_name="members")
    op.drop_column("members", "store_id")

    op.drop_index(op.f("ix_users_store_id"), table_name="users")
    op.drop_column("users", "store_id")
