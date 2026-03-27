"""add inventory and training modules

Revision ID: 20260326_0004
Revises: 20260326_0003
Create Date: 2026-03-26 18:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260326_0004"
down_revision: str | None = "20260326_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="ea"),
        sa.Column("batch_tracking_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expiry_tracking_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )
    op.create_index(op.f("ix_inventory_items_sku"), "inventory_items", ["sku"], unique=True)

    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_inventory_locations_code"), "inventory_locations", ["code"], unique=True)

    op.create_table(
        "inventory_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("doc_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="posted"),
        sa.Column("source_location_id", sa.Integer(), nullable=True),
        sa.Column("target_location_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_location_id"], ["inventory_locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_location_id"], ["inventory_locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_documents_doc_type"), "inventory_documents", ["doc_type"], unique=False)

    op.create_table(
        "inventory_document_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("batch_no", sa.String(length=60), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["inventory_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_document_lines_document_id"), "inventory_document_lines", ["document_id"], unique=False)
    op.create_index(op.f("ix_inventory_document_lines_item_id"), "inventory_document_lines", ["item_id"], unique=False)

    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_reference", sa.String(length=60), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("reserved_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("released_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("released_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_reservations_order_reference"), "inventory_reservations", ["order_reference"], unique=False)
    op.create_index(op.f("ix_inventory_reservations_item_id"), "inventory_reservations", ["item_id"], unique=False)
    op.create_index(op.f("ix_inventory_reservations_location_id"), "inventory_reservations", ["location_id"], unique=False)
    op.create_index(op.f("ix_inventory_reservations_status"), "inventory_reservations", ["status"], unique=False)

    op.create_table(
        "inventory_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=30), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 3), nullable=False),
        sa.Column("reservation_delta", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("document_line_id", sa.Integer(), nullable=True),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("order_reference", sa.String(length=60), nullable=True),
        sa.Column("batch_no", sa.String(length=60), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["inventory_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_line_id"], ["inventory_document_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reservation_id"], ["inventory_reservations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_ledger_item_id"), "inventory_ledger", ["item_id"], unique=False)
    op.create_index(op.f("ix_inventory_ledger_location_id"), "inventory_ledger", ["location_id"], unique=False)
    op.create_index(op.f("ix_inventory_ledger_entry_type"), "inventory_ledger", ["entry_type"], unique=False)
    op.create_index(op.f("ix_inventory_ledger_document_id"), "inventory_ledger", ["document_id"], unique=False)
    op.create_index(op.f("ix_inventory_ledger_order_reference"), "inventory_ledger", ["order_reference"], unique=False)

    op.create_table(
        "quiz_topics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_quiz_topics_code"), "quiz_topics", ["code"], unique=True)

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.String(length=255), nullable=False),
        sa.Column("option_a", sa.String(length=255), nullable=False),
        sa.Column("option_b", sa.String(length=255), nullable=False),
        sa.Column("option_c", sa.String(length=255), nullable=False),
        sa.Column("option_d", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["quiz_topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quiz_questions_topic_id"), "quiz_questions", ["topic_id"], unique=False)

    op.create_table(
        "quiz_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_user_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["quiz_topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quiz_assignments_employee_user_id"), "quiz_assignments", ["employee_user_id"], unique=False)
    op.create_index(op.f("ix_quiz_assignments_topic_id"), "quiz_assignments", ["topic_id"], unique=False)

    op.create_table(
        "spaced_repetition_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_user_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("next_review_date", sa.Date(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("consecutive_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recent_misses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ease_factor", sa.Numeric(6, 3), nullable=False, server_default="2.5"),
        sa.Column("recommendation_reason", sa.String(length=255), nullable=False, server_default="Initial review"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["quiz_topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spaced_repetition_state_employee_user_id"), "spaced_repetition_state", ["employee_user_id"], unique=False)
    op.create_index(op.f("ix_spaced_repetition_state_topic_id"), "spaced_repetition_state", ["topic_id"], unique=False)
    op.create_index(op.f("ix_spaced_repetition_state_next_review_date"), "spaced_repetition_state", ["next_review_date"], unique=False)

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_user_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_answer", sa.String(length=255), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["quiz_topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quiz_attempts_employee_user_id"), "quiz_attempts", ["employee_user_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_topic_id"), "quiz_attempts", ["topic_id"], unique=False)

    op.create_table(
        "review_queue_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_user_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("recommendation_reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["quiz_topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_queue_snapshots_employee_user_id"), "review_queue_snapshots", ["employee_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_queue_snapshots_employee_user_id"), table_name="review_queue_snapshots")
    op.drop_table("review_queue_snapshots")

    op.drop_index(op.f("ix_quiz_attempts_topic_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_employee_user_id"), table_name="quiz_attempts")
    op.drop_table("quiz_attempts")

    op.drop_index(op.f("ix_spaced_repetition_state_next_review_date"), table_name="spaced_repetition_state")
    op.drop_index(op.f("ix_spaced_repetition_state_topic_id"), table_name="spaced_repetition_state")
    op.drop_index(op.f("ix_spaced_repetition_state_employee_user_id"), table_name="spaced_repetition_state")
    op.drop_table("spaced_repetition_state")

    op.drop_index(op.f("ix_quiz_assignments_topic_id"), table_name="quiz_assignments")
    op.drop_index(op.f("ix_quiz_assignments_employee_user_id"), table_name="quiz_assignments")
    op.drop_table("quiz_assignments")

    op.drop_index(op.f("ix_quiz_questions_topic_id"), table_name="quiz_questions")
    op.drop_table("quiz_questions")

    op.drop_index(op.f("ix_quiz_topics_code"), table_name="quiz_topics")
    op.drop_table("quiz_topics")

    op.drop_index(op.f("ix_inventory_ledger_order_reference"), table_name="inventory_ledger")
    op.drop_index(op.f("ix_inventory_ledger_document_id"), table_name="inventory_ledger")
    op.drop_index(op.f("ix_inventory_ledger_entry_type"), table_name="inventory_ledger")
    op.drop_index(op.f("ix_inventory_ledger_location_id"), table_name="inventory_ledger")
    op.drop_index(op.f("ix_inventory_ledger_item_id"), table_name="inventory_ledger")
    op.drop_table("inventory_ledger")

    op.drop_index(op.f("ix_inventory_reservations_status"), table_name="inventory_reservations")
    op.drop_index(op.f("ix_inventory_reservations_location_id"), table_name="inventory_reservations")
    op.drop_index(op.f("ix_inventory_reservations_item_id"), table_name="inventory_reservations")
    op.drop_index(op.f("ix_inventory_reservations_order_reference"), table_name="inventory_reservations")
    op.drop_table("inventory_reservations")

    op.drop_index(op.f("ix_inventory_document_lines_item_id"), table_name="inventory_document_lines")
    op.drop_index(op.f("ix_inventory_document_lines_document_id"), table_name="inventory_document_lines")
    op.drop_table("inventory_document_lines")

    op.drop_index(op.f("ix_inventory_documents_doc_type"), table_name="inventory_documents")
    op.drop_table("inventory_documents")

    op.drop_index(op.f("ix_inventory_locations_code"), table_name="inventory_locations")
    op.drop_table("inventory_locations")

    op.drop_index(op.f("ix_inventory_items_sku"), table_name="inventory_items")
    op.drop_table("inventory_items")
